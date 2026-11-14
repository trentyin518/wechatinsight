"""Stateless CSRF ``state`` for the WeChat OAuth redirect.

The value is a base64url JSON payload (nonce + timestamp) plus an HMAC-SHA256
signature. It needs no server storage and expires after a configurable TTL.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _sign(secret: str, payload: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).hexdigest()


def sign_state(secret: str) -> str:
    payload = _b64(json.dumps({"n": secrets.token_urlsafe(9), "ts": int(time.time())}).encode())
    return f"{payload}.{_sign(secret, payload)}"


def verify_state(secret: str, state: str | None, ttl_seconds: int) -> bool:
    if not state or "." not in state:
        return False
    payload, signature = state.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(secret, payload)):
        return False
    try:
        padded = payload + "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        issued = int(data.get("ts", 0))
    except (ValueError, TypeError):
        return False
    return (int(time.time()) - issued) <= ttl_seconds
