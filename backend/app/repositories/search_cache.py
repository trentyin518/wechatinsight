"""Keyword cache for provider search results.

Cold-start searches are billed per provider call. Storing the outcome per
(provider, keyword) — including the empty outcome — means the same query is
paid for at most once per TTL window.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SearchCache

MAX_KEYWORD_LENGTH = 200


def normalize_keyword(keyword: str) -> str:
    """Collapse whitespace and case so trivial variants share one cache entry."""
    return " ".join((keyword or "").split()).lower()[:MAX_KEYWORD_LENGTH]


def get(session: Session, provider: str, keyword: str) -> SearchCache | None:
    return session.scalar(
        select(SearchCache).where(
            SearchCache.provider == provider,
            SearchCache.keyword == normalize_keyword(keyword),
        )
    )


def is_fresh(
    entry: SearchCache,
    *,
    ttl_hours: int,
    empty_ttl_hours: int,
    now: datetime | None = None,
) -> bool:
    """Empty results are cached longer: they are the ones users retype."""
    now = now or datetime.now(timezone.utc)
    fetched = entry.fetched_at
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    ttl = empty_ttl_hours if entry.total == 0 else ttl_hours
    return now - fetched < timedelta(hours=ttl)


def store(
    session: Session,
    provider: str,
    keyword: str,
    account_ids: list[int],
    *,
    now: datetime | None = None,
) -> SearchCache:
    now = now or datetime.now(timezone.utc)
    normalized = normalize_keyword(keyword)
    entry = get(session, provider, normalized)
    if entry is None:
        entry = SearchCache(
            provider=provider,
            keyword=normalized,
            account_ids=list(account_ids),
            total=len(account_ids),
            fetched_at=now,
        )
        session.add(entry)
    else:
        entry.account_ids = list(account_ids)
        entry.total = len(account_ids)
        entry.fetched_at = now
    session.flush()
    return entry
