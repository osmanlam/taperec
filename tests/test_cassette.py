from __future__ import annotations

import json

import pytest

from taperec.cassette import Cassette, Interaction, TaperecCassetteError


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "cas.json"
    cas = Cassette(path)
    cas.add(
        Interaction(
            method="POST",
            url="https://api.openai.com/v1/chat/completions",
            req_body=json.dumps({"b": 2, "a": 1}),
            status=200,
            resp_headers={"content-type": "application/json"},
            resp_body='{"ok": true}',
        )
    )
    assert path.exists()

    loaded = Cassette.load(str(path))
    assert len(loaded.interactions) == 1
    ix = loaded.interactions[0]
    assert ix.method == "POST"
    assert ix.status == 200
    assert ix.resp_body == '{"ok": true}'
    # JSON request bodies are stored as parsed JSON for readable diffs
    assert ix.req_body_json == {"b": 2, "a": 1}


def test_load_missing_raises(tmp_path):
    with pytest.raises(TaperecCassetteError):
        Cassette.load(str(tmp_path / "nope.json"))


def test_load_rejects_non_cassette(tmp_path):
    p = tmp_path / "junk.json"
    p.write_text("{}")
    with pytest.raises(TaperecCassetteError):
        Cassette.load(str(p))


def test_request_headers_never_persisted(tmp_path):
    path = tmp_path / "cas.json"
    cas = Cassette(path)
    cas.add(Interaction(method="POST", url="https://x/y", req_body="{}", status=200, resp_body="ok"))
    raw = path.read_text()
    # schema has no place for request headers at all
    assert "authorization" not in raw.lower()
    assert "api-key" not in raw.lower()
    assert "headers" in json.loads(raw)["interactions"][0]["response"]
    assert "headers" not in json.loads(raw)["interactions"][0]["request"]
