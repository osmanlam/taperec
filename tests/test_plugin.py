from __future__ import annotations

import pytest

pytest_plugins = ["taperec.pytest_plugin"]

from taperec.pytest_plugin import cassette_path_for, resolve_mode


def test_default_mode_is_replay():
    assert resolve_mode({}) == "replay"


def test_env_mode_record():
    assert resolve_mode({"TAPEREC_MODE": "RECORD"}) == "record"


def test_env_mode_new_episodes():
    assert resolve_mode({"TAPEREC_MODE": "new_episodes"}) == "new_episodes"


def test_bad_mode_rejected():
    with pytest.raises(pytest.UsageError):
        resolve_mode({"TAPEREC_MODE": "turbo"})


def test_cassette_paths_are_per_test(tmp_path):
    module = tmp_path / "test_session.py"
    module.write_text("# module")
    a = cassette_path_for(str(module), "test_alpha")
    b = cassette_path_for(str(module), "test_beta")
    assert a.name == "test_alpha.json"
    assert b.name == "test_beta.json"
    assert a.parent == b.parent == tmp_path / "cassettes"


def test_fixture_yields_taperec(taperec_cassette):
    from taperec import Taperec

    assert isinstance(taperec_cassette, Taperec)
    assert taperec_cassette.mode == "replay"
    assert taperec_cassette.path.name == "test_fixture_yields_taperec.json"
