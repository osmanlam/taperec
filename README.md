<div align="center">

# taperec

**VCR for LLM agent traffic.**

Your agent tests hit the real API → slow, flaky, $$.
`taperec` records the HTTP traffic **once**, then replays it in CI:
deterministic, offline, zero tokens, zero flake. Streams included.

**Record once. Replay forever. Pay nothing.**

[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](https://github.com/osmanlam/taperec/actions)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://pypi.org/project/taperec/)
[![License: MIT](https://img.shields.io/badge/license-MIT-black)](LICENSE)
[![Zero required deps](https://img.shields.io/badge/required_dependencies-0-success)](pyproject.toml)

*works with any httpx-based SDK — `openai`, `anthropic`, and friends*

</div>

---

```console
$ python examples/demo_chat.py

taperec demo — VCR for LLM agent traffic
[1/3] recording 2 interactions against a local fake API ... done (cassette: examples/cassettes/demo.json)
[2/3] fake API stopped — network to it is dead.
[3/3] replaying offline:
      ✓ chat completion  -> identical JSON (200, 13 usage tokens)
      ✓ sse stream       -> identical 3 SSE events
replayed 2 interactions offline — same bytes, zero tokens, zero network.
```

That demo records a chat completion **and** an SSE stream, kills the
server, then replays both byte-identical. That is the whole idea.

## Install

```console
$ pipx install taperec            # CLI only
$ pip install 'taperec[httpx]'    # library use (openai/anthropic SDKs need httpx)
```

## Quickstart (library)

Wrap any httpx-based client. That's it.

```python
import taperec
from openai import OpenAI

# once, locally, against the real API:
with taperec.record("cassettes/agent_run.json"):
    client = OpenAI()
    answer = client.chat.completions.create(model="gpt-4o", messages=[...])

# forever after, in CI — no API key, no network, no tokens:
with taperec.replay("cassettes/agent_run.json"):
    client = OpenAI()
    answer = client.chat.completions.create(model="gpt-4o", messages=[...])
    # byte-identical to the recorded response, SSE streams included
```

Unmatched request in replay mode → loud, actionable error (never a silent
wrong answer):

```text
taperec: no cassette match for POST https://api.openai.com/v1/chat/completions
  cassette: cassettes/agent_run.json
  body:     '{"messages": [{"content": "unmatched", ...
  nearest:  POST https://api.openai.com/v1/chat/completions (same url, different body)
  hint: re-record with taperec.new_episodes(...) or mode=new_episodes
```

## Quickstart (pytest)

```python
# conftest.py
pytest_plugins = ["taperec.pytest_plugin"]
```

```python
# test_agent.py — one cassette per test, automatically
def test_agent_plans_trip(taperec_cassette):
    with taperec_cassette:
        agent = MyAgent()          # its LLM calls are now served from tape
        assert agent.plan("paris") == EXPECTED_PLAN
```

```console
$ TAPEREC_MODE=record pytest -q test_agent.py   # local: (re)record cassettes
$ pytest -q                                     # CI: replay offline (default)
```

## Modes

| mode | cassette hit | cassette miss |
|---|---|---|
| `record` | — | live call, **cassette rewritten** |
| `replay` | served from tape | `TaperecError` (CI default) |
| `new_episodes` | served from tape | live call, appended |

## How matching works

A request matches an interaction when **method + URL path + canonical body**
are equal. JSON bodies are canonicalized (sorted keys), so `{"a":1,"b":2}`
matches `{"b":2,"a":1}`. Host, port and query string are ignored on purpose:
a cassette recorded against a live endpoint replays identically when the
client points at a dead port in CI. Streams are buffered when recorded and
replayed byte-identical.

## Cassettes are safe by design

- plain JSON, sorted keys, pretty-printed — they diff cleanly in code review
- request headers are **never persisted**, so `Authorization` / `x-api-key`
  secrets cannot leak into your repo
- `taperec verify cassettes/` fails CI if a cassette contains secrets or a broken schema

## Compared to

| | hand-rolled mocks | [VCR.py](https://github.com/kevin1024/vcrpy) | [agent-vcr](https://pypi.org/project/agent-vcr/) | **taperec** |
|---|---|---|---|---|
| Layer | your code | HTTP | MCP | **HTTP (LLM SDKs)** |
| JSON-body canonicalization | — | — | — | ✔ key order never breaks a match |
| SSE streaming replay | — | partial | — | ✔ byte-identical |
| Works with openai/anthropic SDKs | ✔ (you write them) | partially | ✔ (MCP only) | ✔ |
| Near-miss error messages | — | partial | — | ✔ |
| Secret redaction | manual | partial | — | ✔ headers never stored |
| Required dependencies | 0 | several | several | **0** |

## Honest limitations (v0.1)

- intercepts **httpx** only (that covers `openai`, `anthropic`, and most
  2026 agent frameworks; `aiohttp`/`urllib` transports are on the roadmap)
- streams are buffered on record — memory, not semantics, trade-off
- replay reconstructs the recorded response; it cannot invent one

## Roadmap

- [ ] `aiohttp` + `urllib` transports
- [ ] `--taperec-strict`: fail if a test's cassette had zero replays
- [ ] token-cost assertions (`assert cassette.tokens < 500`)
- [ ] cassette diffing (`taperec diff old.json new.json`)

## Contributing

PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Deterministic,
offline tests only.

## License

[MIT](LICENSE) © 2026 osmanlam
