"""The Taperec recorder: monkeypatches httpx send() to record or replay.

Works with any httpx-based client — the `openai` and `anthropic` SDKs both
qualify. Streams are buffered on record (the caller receives a fully
buffered httpx.Response; iteration still works), and replayed byte-identical.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .cassette import Cassette, Interaction
from .match import find_match

MODES = ("record", "replay", "new_episodes")


class TaperecError(RuntimeError):
    pass


class Taperec:
    def __init__(self, mode: str, cassette_path: str):
        if mode not in MODES:
            raise TaperecError(f"unknown mode {mode!r}; expected one of {MODES}")
        self.mode = mode
        self.path = Path(cassette_path)
        self._cassette: Optional[Cassette] = None
        self._orig = {}

    # -- context manager ----------------------------------------------------
    def __enter__(self) -> "Taperec":
        try:
            import httpx  # noqa: F401
        except ImportError as exc:  # pragma: no cover - depends on env
            raise TaperecError(
                "taperec needs httpx to intercept traffic "
                "(used by the openai/anthropic SDKs). Install it with: "
                "pip install 'taperec[httpx]'"
            ) from exc

        # record starts from a blank cassette (re-records replace);
        # replay/new_episodes reuse what is already on tape
        if self.mode == "record" or not self.path.exists():
            self._cassette = Cassette(self.path)
        else:
            self._cassette = Cassette.load(self.path)

        import httpx

        self._orig = {
            "sync": httpx.Client.send,
            "async": httpx.AsyncClient.send,
        }
        httpx.Client.send = self._patch_sync(self._orig["sync"])
        httpx.AsyncClient.send = self._patch_async(self._orig["async"])
        return self

    def __exit__(self, *exc) -> None:
        import httpx

        if "sync" in self._orig:
            httpx.Client.send = self._orig["sync"]
            httpx.AsyncClient.send = self._orig["async"]
        self._orig = {}

    # -- patching -----------------------------------------------------------
    def _patch_sync(self, original):
        def send(client, request, *args, **kwargs):
            replayed = self._maybe_replay(request)
            if replayed is not None:
                return replayed
            response = original(client, request, *args, **kwargs)
            raw = response.read()  # drains streams too
            try:
                response.close()
            except Exception:
                pass
            return self._store_and_clone(request, response, raw)

        return send

    def _patch_async(self, original):
        async def send(client, request, *args, **kwargs):
            replayed = self._maybe_replay(request)
            if replayed is not None:
                return replayed
            response = await original(client, request, *args, **kwargs)
            raw = await response.aread()
            try:
                await response.aclose()
            except Exception:
                pass
            return self._store_and_clone(request, response, raw)

        return send

    # -- core ---------------------------------------------------------------
    def _maybe_replay(self, request):
        """Replay response for a cassette hit; None to pass through live."""
        if self.mode == "record":
            return None
        body = self._read_request_body(request)
        hit, near = find_match(
            self._cassette.interactions, request.method, str(request.url), body
        )
        if hit is None:
            if self.mode == "replay":
                raise TaperecError(self._miss_message(request, body, near))
            return None  # new_episodes: record it live

        import httpx

        return httpx.Response(
            hit.status,
            headers=hit.resp_headers,
            content=hit.resp_body.encode("utf-8"),
            request=request,
        )

    def _store_and_clone(self, request, response, raw: bytes):
        import httpx

        self._cassette.add(
            Interaction(
                method=request.method,
                url=str(request.url),
                req_body=self._read_request_body(request),
                status=response.status_code,
                resp_headers={k: v for k, v in response.headers.items()},
                resp_body=raw.decode("utf-8", errors="replace"),
            )
        )
        # hand back a buffered clone so streaming callers still work
        return httpx.Response(
            response.status_code,
            headers=dict(response.headers),
            content=raw,
            request=request,
        )

    def _read_request_body(self, request) -> str:
        try:
            return request.read().decode("utf-8", errors="replace")
        except Exception:
            return ""

    def _miss_message(self, request, body: str, near) -> str:
        msg = (
            f"taperec: no cassette match for {request.method} {request.url}\n"
            f"  cassette: {self.path}\n"
            f"  body:     {body[:200]!r}\n"
        )
        if near is not None:
            msg += f"  nearest:  {near.method} {near.url} (same url, different body)\n"
        msg += "  hint: re-record with taperec.new_episodes(...) or mode=new_episodes"
        return msg


# -- convenience constructors ---------------------------------------------
def record(cassette_path: str) -> Taperec:
    """Pass through to the real API, saving every interaction."""
    return Taperec("record", cassette_path)


def replay(cassette_path: str) -> Taperec:
    """Serve every interaction from cassette; never touch the network."""
    return Taperec("replay", cassette_path)


def new_episodes(cassette_path: str) -> Taperec:
    """Replay known interactions; record and append unknown ones."""
    return Taperec("new_episodes", cassette_path)
