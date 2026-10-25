"""Offline demo: record → stop server → replay. Run with:

    python examples/demo_chat.py

Starts a fake OpenAI-style API on localhost, records a chat completion and
an SSE stream into examples/cassettes/demo.json, shuts the server down,
then replays both interactions with the network dead.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
CASSETTE = HERE / "cassettes" / "demo.json"
DEAD_URL = "http://127.0.0.1:9/v1"  # nothing listens here

CHAT_JSON = {
    "id": "chatcmpl-demo",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello from fake"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 9, "completion_tokens": 4, "total_tokens": 13},
}
SSE_BODY = (
    'data: {"choices":[{"index":0,"delta":{"content":"Hel"}}]}\n\n'
    'data: {"choices":[{"index":0,"delta":{"content":"lo!"}}]}\n\n'
    "data: [DONE]\n\n"
).encode("utf-8")


class FakeAPI(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        stream = b'"stream":true' in body.replace(b" ", b"")
        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(SSE_BODY)))
            self.end_headers()
            self.wfile.write(SSE_BODY)
        else:
            raw = json.dumps(CHAT_JSON).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    def log_message(self, *args):
        pass


def chat(client) -> dict:
    r = client.post(
        "/chat/completions",
        json={"model": "demo", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": "Bearer sk-demo-secret"},
    )
    r.raise_for_status()
    return r.json()


def stream(client) -> list:
    events = []
    with client.stream(
        "POST", "/chat/completions", json={"model": "demo", "stream": True, "messages": [{"role": "user", "content": "hi"}]}
    ) as r:
        for line in r.iter_lines():
            if line.startswith("data:"):
                events.append(line)
    return events


def main() -> int:
    import httpx

    import taperec

    print("taperec demo — VCR for LLM agent traffic")

    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeAPI)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    live_url = f"http://127.0.0.1:{server.server_address[1]}/v1"

    print("[1/3] recording 2 interactions against a local fake API ...", end=" ")
    with taperec.record(str(CASSETTE)):
        with httpx.Client(base_url=live_url) as c:
            expected_chat = chat(c)
            expected_stream = stream(c)
    server.shutdown()
    server.server_close()
    print(f"done (cassette: {CASSETTE.relative_to(HERE.parent)})")

    print("[2/3] fake API stopped — network to it is dead.")
    assert not CASSETTE.read_text().count("sk-demo-secret"), "secret leaked!"

    print("[3/3] replaying offline:")
    with taperec.replay(str(CASSETTE)):
        with httpx.Client(base_url=DEAD_URL) as c:
            got_chat = chat(c)
            got_stream = stream(c)
    assert got_chat == expected_chat, "chat replay differs!"
    assert got_stream == expected_stream, "stream replay differs!"
    print("      ✓ chat completion  -> identical JSON (200, 13 usage tokens)")
    print(f"      ✓ sse stream       -> identical {len(got_stream)} SSE events")
    print("replayed 2 interactions offline — same bytes, zero tokens, zero network.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
