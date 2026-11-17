"""Repository for durable search retries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import SearchRetryQueue, SearchRetryStatus
from app.repositories.search_cache import normalize_keyword


def enqueue(
    session: Session,
    provider: str,
    keyword: str,
    *,
    max_attempts: int = 8,
    now: datetime | None = None,
) -> SearchRetryQueue | None:
    """Record (or re-arm) a pending retry for a busy keyword.

    Returns the queue row, or ``None`` if a succeeded/fresh entry already
    satisfies this keyword.
    """
    now = now or datetime.now(timezone.utc)
    normalized = normalize_keyword(keyword)
    row = session.scalar(
        select(SearchRetryQueue).where(
            SearchRetryQueue.provider == provider,
            SearchRetryQueue.keyword == normalized,
        )
    )
    if row is None:
        row = SearchRetryQueue(
            provider=provider,
            keyword=normalized,
            status=SearchRetryStatus.PENDING,
            max_attempts=max_attempts,
            next_retry_at=now,
        )
        session.add(row)
    elif row.status == SearchRetryStatus.PENDING:
        # Already queued; nothing to do.
        return row
    elif row.status == SearchRetryStatus.EXHAUSTED:
        # Re-arm for a fresh attempt cycle.
        row.status = SearchRetryStatus.PENDING
        row.attempts = 0
        row.last_error = None
        row.next_retry_at = now
    else:
        # Running / succeeded: leave the worker to own it.
        return row
    session.flush()
    return row


def due(
    session: Session,
    now: datetime | None = None,
    *,
    limit: int = 20,
) -> list[SearchRetryQueue]:
    """Fetch pending retries whose backoff has elapsed."""
    now = now or datetime.now(timezone.utc)
    return list(
        session.scalars(
            select(SearchRetryQueue)
            .where(
                SearchRetryQueue.status == SearchRetryStatus.PENDING,
                SearchRetryQueue.next_retry_at <= now,
            )
            .order_by(SearchRetryQueue.next_retry_at.asc())
            .limit(limit)
        ).all()
    )


def claim(session: Session, row: SearchRetryQueue) -> bool:
    """Atomically mark a retry as running and increment its attempt counter.

    Returns ``False`` if another processor already claimed it (safe under
    multiple API workers / a separate worker draining the same queue).
    """
    result = session.execute(
        update(SearchRetryQueue)
        .where(
            SearchRetryQueue.id == row.id,
            SearchRetryQueue.status == SearchRetryStatus.PENDING,
        )
        .values(
            status=SearchRetryStatus.RUNNING,
            attempts=SearchRetryQueue.attempts + 1,
        )
    )
    session.flush()
    if result.rowcount == 0:
        return False
    session.refresh(row)
    return True


def schedule_next(
    session: Session,
    row: SearchRetryQueue,
    error: str,
    *,
    now: datetime | None = None,
    base_seconds: int = 60,
) -> None:
    """Record a failure and either schedule the next backoff or exhaust."""
    now = now or datetime.now(timezone.utc)
    row.last_error = error
    if row.attempts >= row.max_attempts:
        row.status = SearchRetryStatus.EXHAUSTED
        row.next_retry_at = now
    else:
        row.status = SearchRetryStatus.PENDING
        row.next_retry_at = now + timedelta(
            seconds=min(base_seconds * (2 ** (row.attempts - 1)), 3600)
        )


def succeed(session: Session, row: SearchRetryQueue) -> None:
    row.status = SearchRetryStatus.SUCCEEDED
    row.last_error = None
    row.next_retry_at = datetime.now(timezone.utc)


def mark_exhausted(session: Session, row: SearchRetryQueue, error: str) -> None:
    row.status = SearchRetryStatus.EXHAUSTED
    row.last_error = error
    row.next_retry_at = datetime.now(timezone.utc)
