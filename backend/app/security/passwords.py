"""Security primitives: password hashing.

Password hashing uses PBKDF2-HMAC-SHA256 from the standard library so the app
needs no extra binary dependency (works in the plain venv). Format is
``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_PBKDF2_ITERATIONS = 240_000
_ALGORITHM = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("密码不能为空")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"{_ALGORITHM}${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not password:
        return False
    try:
        algorithm, iterations_raw, salt_hex, hash_hex = stored.split("$")
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_raw)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, TypeError):
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)
