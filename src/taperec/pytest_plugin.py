"""pytest plugin: one cassette per test, mode from TAPEREC_MODE.

In conftest.py::

    pytest_plugins = ["taperec.pytest_plugin"]

In a test::

    def test_agent_answers(taperec_cassette):
        with taperec_cassette:
            client = openai.OpenAI()
            ...

Local development (writes/updates cassettes)::

    TAPEREC_MODE=record pytest -q

CI (the default): replays offline, zero tokens, deterministic.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from .recorder import MODES, Taperec


def resolve_mode(env=None) -> str:
    env = os.environ if env is None else env
    mode = env.get("TAPEREC_MODE", "replay").strip().lower()
    if mode not in MODES:
        raise pytest.UsageError(
            f"TAPEREC_MODE={mode!r} is invalid; use one of {MODES}"
        )
    return mode


def cassette_path_for(module_file: str, test_name: str) -> Path:
    return Path(module_file).parent / "cassettes" / f"{test_name}.json"


@pytest.fixture
def taperec_cassette(request) -> Taperec:
    mode = resolve_mode()
    path = cassette_path_for(request.module.__file__, request.node.name)
    with Taperec(mode, path) as tr:
        yield tr
