"""Request matching: canonical JSON bodies, method + URL path.

The host:port is deliberately IGNORED when matching: cassettes recorded
against a live endpoint replay identically when the client points anywhere
else (dead port, proxy, CI runner). LLM API paths (/v1/chat/completions,
/v1/messages, ...) are distinctive enough that this is safe in practice.
"""

from __future__ import annotations

import json
from typing import Optional, Tuple
from urllib.parse import urlsplit

from .cassette import Interaction


def url_key(url: str) -> str:
    """Host and query string are dropped; only the path keys the match."""
    return urlsplit(url).path or "/"


def canonical_body(body: str) -> str:
    """JSON bodies are canonicalized so key order never breaks a match."""
    try:
        return json.dumps(json.loads(body), sort_keys=True, separators=(",", ":"))
    except (ValueError, TypeError):
        return body


def request_key(method: str, url: str, body: str) -> Tuple[str, str, str]:
    return (method.upper(), url_key(url), canonical_body(body))


def find_match(
    interactions, method: str, url: str, body: str
) -> Tuple[Optional[Interaction], Optional[Interaction]]:
    """Return (exact_match, near_miss).

    near_miss is an interaction with the same method+path but a different
    canonical body — used to build helpful replay errors.
    """
    key = request_key(method, url, body)
    near: Optional[Interaction] = None
    for ix in interactions:
        ix_key = request_key(ix.method, ix.url, ix.req_body or _json_of(ix))
        if ix_key == key:
            return ix, None
        if ix_key[:2] == key[:2]:
            near = near or ix
    return None, near


def _json_of(ix: Interaction) -> str:
    if ix.req_body_json is None:
        return ""
    return json.dumps(ix.req_body_json, sort_keys=True, separators=(",", ":"))
