"""Search-result cache: identical keywords must not hit a billed provider twice."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.db.models import SearchCache
from app.providers.mock import MockProvider
from app.repositories import search_cache as search_cache_repo
from app.services import accounts as accounts_service
from app.services.ratelimit import rate_limiter


def _settings(**overrides):
    base = get_settings()
    data = dict(base.__dict__)
    data.update(overrides)
    return base.__class__(**data)


class CountingProvider(MockProvider):
    def __init__(self) -> None:
        self.calls = 0

    async def search_accounts(self, keyword: str, *, page: int = 1, page_size: int = 20):
        self.calls += 1
        return await super().search_accounts(keyword, page=page, page_size=page_size)


async def test_positive_result_is_cached_and_reused(session):
    rate_limiter.reset()
    provider = CountingProvider()
    settings = _settings()

    first = await accounts_service.search_accounts(
        session, "示例", 1, 20, provider=provider, settings=settings
    )
    assert first.total > 0
    assert provider.calls == 1

    second = await accounts_service.search_accounts(
        session, "示例", 1, 20, provider=provider, settings=settings
    )
    assert second.total == first.total
    assert provider.calls == 1  # served from DB / cache, no new spend


async def test_empty_result_is_cached_too(session):
    rate_limiter.reset()
    provider = CountingProvider()
    settings = _settings()

    first = await accounts_service.search_accounts(
        session, "汽车之家", 1, 20, provider=provider, settings=settings
    )
    assert first.total == 0
    assert provider.calls == 1

    second = await accounts_service.search_accounts(
        session, "汽车之家", 1, 20, provider=provider, settings=settings
    )
    assert second.total == 0
    assert provider.calls == 1  # the negative result is remembered

    entry = session.query(SearchCache).one()
    assert entry.keyword == "汽车之家"
    assert entry.total == 0


async def test_keyword_variants_share_one_cache_entry(session):
    rate_limiter.reset()
    provider = CountingProvider()
    settings = _settings()

    await accounts_service.search_accounts(
        session, "  Car  Home  ", 1, 20, provider=provider, settings=settings
    )
    await accounts_service.search_accounts(
        session, "car home", 1, 20, provider=provider, settings=settings
    )
    assert provider.calls == 1


async def test_stale_cache_triggers_one_refetch(session):
    rate_limiter.reset()
    provider = CountingProvider()
    settings = _settings(search_cache_ttl_hours=1, empty_search_cache_ttl_hours=1)

    await accounts_service.search_accounts(
        session, "汽车之家", 1, 20, provider=provider, settings=settings
    )
    entry = session.query(SearchCache).one()
    entry.fetched_at = datetime.now(timezone.utc) - timedelta(hours=5)
    session.commit()

    await accounts_service.search_accounts(
        session, "汽车之家", 1, 20, provider=provider, settings=settings
    )
    assert provider.calls == 2


def test_freshness_uses_longer_ttl_for_empty_results() -> None:
    now = datetime.now(timezone.utc)
    entry = SearchCache(
        provider="mock", keyword="x", account_ids=[], total=0, fetched_at=now - timedelta(hours=48)
    )
    assert search_cache_repo.is_fresh(
        entry, ttl_hours=24, empty_ttl_hours=168, now=now
    )
    assert not search_cache_repo.is_fresh(
        entry, ttl_hours=24, empty_ttl_hours=24, now=now
    )
