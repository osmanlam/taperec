"""Cassette persistence: JSON, sorted keys, pretty-printed, diff-friendly.

Security: request headers are never persisted at all (we only need method,
url and body to match, and only status/headers/body to replay), so API keys
in Authorization / x-api-key headers can never leak into a cassette.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

CASSETTE_VERSION = 1


@dataclass
class Interaction:
    method: str
    url: str
    req_body: str = ""
    status: int = 200
    resp_headers: dict = field(default_factory=dict)
    resp_body: str = ""
    # canonical parsed JSON of req_body when parseable (for readable diffs)
    req_body_json: Optional[Any] = None

    def __post_init__(self) -> None:
        if self.req_body_json is None and self.req_body:
            self.req_body_json = _maybe_json(self.req_body)

    def to_dict(self) -> dict:
        req: dict = {"method": self.method, "url": self.url}
        if self.req_body_json is not None:
            req["body_json"] = self.req_body_json
        elif self.req_body:
            req["body_text"] = self.req_body
        return {
            "request": req,
            "response": {
                "status": self.status,
                "headers": dict(self.resp_headers),
                "body": self.resp_body,
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Interaction":
        req = d["request"]
        resp = d["response"]
        return cls(
            method=req["method"],
            url=req["url"],
            req_body_json=req.get("body_json"),
            req_body=req.get("body_text", ""),
            status=resp["status"],
            resp_headers=dict(resp.get("headers", {})),
            resp_body=resp.get("body", ""),
        )


def _maybe_json(text: str) -> Optional[Any]:
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


class Cassette:
    def __init__(self, path: str, interactions: Optional[List[Interaction]] = None):
        self.path = Path(path)
        self.interactions: List[Interaction] = interactions or []

    def add(self, interaction: Interaction) -> None:
        self.interactions.append(interaction)
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": CASSETTE_VERSION,
            "recorded_at": _now_iso(),
            "interactions": [i.to_dict() for i in self.interactions],
        }
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str) -> "Cassette":
        p = Path(path)
        if not p.exists():
            raise TaperecCassetteError(f"cassette not found: {p}")
        data = json.loads(p.read_text(encoding="utf-8"))
        if "interactions" not in data or "version" not in data:
            raise TaperecCassetteError(f"not a taperec cassette: {p}")
        return cls(p, [Interaction.from_dict(d) for d in data["interactions"]])


class TaperecCassetteError(RuntimeError):
    pass


def _now_iso() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
