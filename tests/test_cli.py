from __future__ import annotations

import json

from taperec.cli import main


def _make_cassette(tmp_path):
    path = tmp_path / "cas.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "recorded_at": "2026-10-25T00:00:00+00:00",
                "interactions": [
                    {
                        "request": {"method": "POST", "url": "https://api.x.com/v1/chat", "body_json": {"a": 1}},
                        "response": {"status": 200, "headers": {"content-type": "application/json"}, "body": "{}"},
                    }
                ],
            },
            indent=2,
        )
    )
    return path


def test_show_summary(tmp_path, capsys):
    path = _make_cassette(tmp_path)
    assert main(["show", str(path)]) == 0
    out = capsys.readouterr().out
    assert "POST" in out and "api.x.com" in out and "200" in out
    assert "1 interactions" in out


def test_show_json(tmp_path, capsys):
    path = _make_cassette(tmp_path)
    assert main(["show", str(path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["version"] == 1


def test_verify_ok(tmp_path, capsys):
    path = _make_cassette(tmp_path)
    assert main(["verify", str(path)]) == 0
    assert "✓" in capsys.readouterr().out


def test_verify_fails_on_secret(tmp_path, capsys):
    path = _make_cassette(tmp_path)
    data = json.loads(path.read_text())
    data["interactions"][0]["request"]["headers"] = {"Authorization": "Bearer sk-leak"}
    path.write_text(json.dumps(data))
    assert main(["verify", str(path)]) == 1
    assert "redaction failure" in capsys.readouterr().out


def test_verify_missing_file(tmp_path, capsys):
    assert main(["verify", str(tmp_path / "nope.json")]) == 1
