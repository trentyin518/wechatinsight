"""Server-side sessions: issue high-entropy tokens, store only their hash.

A login yields a random opaque token. The DB stores ``sha256(token)`` so a DB
leak cannot be replayed. Sessions are revocable (logout / admin) and expire.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User, UserSession


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    # SQLite returns naive datetimes; treat stored timestamps as UTC.
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def create_session(
    session: Session,
    user_id: int,
    ttl_hours: int,
    *,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, UserSession]:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    row = UserSession(
        user_id=user_id,
        token_hash=_hash_token(token),
        expires_at=expires_at,
        user_agent=(user_agent or None),
        ip=(ip or None),
    )
    session.add(row)
    session.flush()
    return token, row


def resolve_user(session: Session, token: str | None) -> User | None:
    if not token:
        return None
    row = session.scalar(
        select(UserSession).where(UserSession.token_hash == _hash_token(token))
    )
    if row is None or row.revoked_at is not None:
        return None
    if _aware(row.expires_at) <= datetime.now(timezone.utc):
        return None
    return session.get(User, row.user_id)


def revoke_session(session: Session, token: str | None) -> None:
    if not token:
        return
    row = session.scalar(
        select(UserSession).where(UserSession.token_hash == _hash_token(token))
    )
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        session.flush()


def revoke_all_for_user(session: Session, user_id: int) -> None:
    now = datetime.now(timezone.utc)
    for row in session.scalars(
        select(UserSession).where(
            UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
        )
    ):
        row.revoked_at = now
    session.flush()
