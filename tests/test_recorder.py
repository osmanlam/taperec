from __future__ import annotations

import json

import httpx
import pytest

from conftest import REQUEST_COUNT
from taperec import new_episodes, record, replay
from taperec.recorder import Taperec, TaperecError

AUTH_HEADERS = {"Authorization": "Bearer sk-secret-do-not-store"}


def _client(base_url):
    return httpx.Client(base_url=base_url, headers=AUTH_HEADERS)


def _chat(client, **over):
    payload = {"model": "gpt-fake", "messages": [{"role": "user", "content": "hi"}]}
    payload.update(over)
    r = client.post("/chat/completions", json=payload)
    r.raise_for_status()
    return r.json()


def _stream(client):
    payload = {"model": "gpt-fake", "stream": True, "messages": [{"role": "user", "content": "hi"}]}
    chunks = []
    with client.stream("POST", "/chat/completions", json=payload) as r:
        for line in r.iter_lines():
            if line.startswith("data:"):
                chunks.append(line)
    return chunks


def test_record_writes_cassette_and_redacts(fake_llm_url, tmp_path):
    cas = tmp_path / "c.json"
    with record(str(cas)):
        with _client(fake_llm_url) as c:
            out = _chat(c)
    assert out["choices"][0]["message"]["content"] == "Hello from fake"
    raw = cas.read_text()
    assert "sk-secret-do-not-store" not in raw
    assert "authorization" not in raw.lower()


def test_replay_works_with_server_gone(fake_llm_url, tmp_path):
    cas = tmp_path / "c.json"
    with record(str(cas)):
        with _client(fake_llm_url) as c:
            expected = _chat(c)
            streamed = _stream(c)

    # Server is down for good: point at a dead port, cassette must serve.
    dead_url = "http://127.0.0.1:9/v1"  # port 9 = discard, nothing listens
    before = REQUEST_COUNT["n"]
    with replay(str(cas)):
        with _client(dead_url) as c:
            assert _chat(c) == expected
            assert _stream(c) == streamed
    assert REQUEST_COUNT["n"] == before, "replay must not touch the network"


def test_replay_is_deterministic(fake_llm_url, tmp_path):
    cas = tmp_path / "c.json"
    with record(str(cas)):
        with _client(fake_llm_url) as c:
            _chat(c)
    results = []
    for _ in range(2):
        with replay(str(cas)):
            with _client("http://127.0.0.1:9/v1") as c:
                results.append(_chat(c))
    assert results[0] == results[1]


def test_replay_miss_raises_with_hint(fake_llm_url, tmp_path):
    cas = tmp_path / "c.json"
    with record(str(cas)):
        with _client(fake_llm_url) as c:
            _chat(c, messages=[{"role": "user", "content": "original"}])
    with replay(str(cas)):
        with _client("http://127.0.0.1:9/v1") as c:
            with pytest.raises(TaperecError) as exc:
                _chat(c, messages=[{"role": "user", "content": "unmatched"}])
    msg = str(exc.value)
    assert str(cas) in msg
    assert "nearest" in msg and "different body" in msg
    assert "new_episodes" in msg


def test_new_episodes_mixes_cassette_and_live(fake_llm_url, tmp_path):
    cas = tmp_path / "c.json"
    with record(str(cas)):
        with _client(fake_llm_url) as c:
            _chat(c, messages=[{"role": "user", "content": "known"}])

    before = REQUEST_COUNT["n"]
    with new_episodes(str(cas)):
        with _client(fake_llm_url) as c:
            # known interaction: served from cassette, no network
            _chat(c, messages=[{"role": "user", "content": "known"}])
            assert REQUEST_COUNT["n"] == before
            # unknown interaction: recorded live
            _chat(c, messages=[{"role": "user", "content": "fresh"}])
            assert REQUEST_COUNT["n"] == before + 1

    data = json.loads(cas.read_text())
    assert len(data["interactions"]) == 2


def test_async_client_replays(fake_llm_url, tmp_path):
    import asyncio

    cas = tmp_path / "c.json"
    with record(str(cas)):
        with _client(fake_llm_url) as c:
            expected = _chat(c)

    async def run():
        with replay(str(cas)):
            async with httpx.AsyncClient(
                base_url="http://127.0.0.1:9/v1", headers=AUTH_HEADERS
            ) as c:
                r = await c.post(
                    "/chat/completions",
                    json={"model": "gpt-fake", "messages": [{"role": "user", "content": "hi"}]},
                )
                return r.json()

    assert asyncio.new_event_loop().run_until_complete(run()) == expected


def test_unknown_mode_rejected(tmp_path):
    with pytest.raises(TaperecError):
        Taperec("fast-forward", str(tmp_path / "x.json"))
