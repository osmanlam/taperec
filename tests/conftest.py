"""A fake OpenAI-style server for offline tests: chat completions (plain
JSON and SSE streaming) + embeddings. Counts requests so tests can prove
replay never touches the network."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

REQUEST_COUNT = {"n": 0}

CHAT_JSON = {
    "id": "chatcmpl-fake1",
    "object": "chat.completion",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "Hello from fake"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 9, "completion_tokens": 4, "total_tokens": 13},
}

SSE_BODY = (
    'data: {"id":"chatcmpl-fake1","choices":[{"index":0,"delta":{"role":"assistant"}}]}\n\n'
    'data: {"id":"chatcmpl-fake1","choices":[{"index":0,"delta":{"content":"Hel"}}]}\n\n'
    'data: {"id":"chatcmpl-fake1","choices":[{"index":0,"delta":{"content":"lo!"}}]}\n\n'
    "data: [DONE]\n\n"
).encode("utf-8")


class FakeHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - http.server API
        REQUEST_COUNT["n"] += 1
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(body or b"{}")
        except ValueError:
            payload = {}

        if self.path.startswith("/v1/chat/completions"):
            if payload.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(SSE_BODY)))
                self.end_headers()
                self.wfile.write(SSE_BODY)
            else:
                self._json(200, CHAT_JSON)
        elif self.path.startswith("/v1/embeddings"):
            self._json(
                200,
                {"object": "list", "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}]},
            )
        else:
            self._json(404, {"error": "not found"})

    def _json(self, status: int, obj: dict) -> None:
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):  # silence request logs
        pass


@pytest.fixture
def fake_llm_url(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    REQUEST_COUNT["n"] = 0
    yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    server.shutdown()
    server.server_close()
