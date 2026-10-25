# Contributing to taperec

Thanks for helping! Small, focused PRs win.

## Setup

```console
$ git clone https://github.com/osmanlam/taperec
$ cd taperec && python -m venv .venv && .venv/bin/pip install -e .[dev]
$ .venv/bin/pytest -q          # everything must pass, offline
$ python examples/demo_chat.py # must exit 0
```

## Ground rules

- Python 3.9+ compatibility, zero required runtime dependencies (httpx stays an optional extra).
- Cassettes must never contain secrets: request headers are not persisted — keep it that way.
- Deterministic tests only: no sleeps, no live network, no tokens.
- New features: open an issue first with a cassette-shaped example.

## Reporting bugs

Include: the SDK + version, the cassette (redact anything sensitive — `taperec verify` checks), and a minimal repro.
