from __future__ import annotations

from taperec.cassette import Interaction
from taperec.match import canonical_body, find_match, request_key, url_key


def _ix(method="POST", url="https://api.x.com/v1/chat", body='{"a":1,"b":2}'):
    return Interaction(method=method, url=url, req_body=body, status=200, resp_body="ok")


def test_canonical_body_sorts_json_keys():
    assert canonical_body('{"b":2,"a":1}') == canonical_body('{"a":1,"b":2}')
    assert canonical_body("plain text") == "plain text"


def test_url_key_uses_path_only():
    assert url_key("https://x.com/v1/chat?beta=2&alpha=1") == "/v1/chat"
    assert url_key("http://other.example:9999/v1/chat") == "/v1/chat"


def test_exact_match_ignores_key_order_query_and_host():
    cas = [_ix()]
    hit, near = find_match(
        cas, "POST", "http://127.0.0.1:9/v1/chat?x=1", '{"b":2,"a":1}'
    )
    assert hit is cas[0]
    assert near is None


def test_near_miss_same_path_different_body():
    cas = [_ix(body='{"a":1}')]
    hit, near = find_match(cas, "POST", "https://api.x.com/v1/chat", '{"a":2}')
    assert hit is None
    assert near is cas[0]


def test_no_match_on_different_path():
    cas = [_ix()]
    hit, near = find_match(cas, "POST", "https://api.x.com/v1/other", '{"a":1,"b":2}')
    assert hit is None
    assert near is None


def test_method_matters():
    cas = [_ix(method="GET")]
    hit, _ = find_match(cas, "POST", "https://api.x.com/v1/chat", '{"a":1,"b":2}')
    assert hit is None


def test_request_key_stable():
    assert request_key("post", "https://x/a?q=1", '{"b":2,"a":1}') == request_key(
        "POST", "http://y.z:1/a", '{"a":1,"b":2}'
    )
