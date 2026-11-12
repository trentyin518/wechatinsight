"""Account query service: local-first search with controlled cold start."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import DataSourceUnavailable, QuotaExceeded
from app.db.models import WechatAccount
from app.providers.base import WeChatProvider
from app.providers.registry import get_provider
from app.repositories import accounts as accounts_repo
from app.repositories import search_cache as search_cache_repo
from app.repositories import usage as usage_repo
from app.services.ratelimit import rate_limiter


@dataclass(slots=True)
class SearchResult:
    items: list[WechatAccount]
    total: int
    degraded: bool = False


async def search_accounts(
    session: Session,
    keyword: str,
    page: int,
    page_size: int,
    *,
    provider: WeChatProvider | None = None,
    settings: Settings | None = None,
) -> SearchResult:
    settings = settings or get_settings()
    items, total = accounts_repo.search_local(session, keyword, page, page_size)
    if total > 0 or not (keyword or "").strip():
        return SearchResult(items=items, total=total)

    if not settings.allow_cold_start_search:
        return SearchResult(items=items, total=total)

    provider_name = getattr(provider, "name", None) or settings.default_provider

    # A keyword we already paid for — including one that returned nothing — is
    # answered from the cache. No rate-limit slot, no provider call, no cost.
    cached = search_cache_repo.get(session, provider_name, keyword)
    if cached is not None and search_cache_repo.is_fresh(
        cached,
        ttl_hours=settings.search_cache_ttl_hours,
        empty_ttl_hours=settings.empty_search_cache_ttl_hours,
    ):
        cached_items, cached_total = _items_from_ids(session, cached.account_ids, page, page_size)
        return SearchResult(items=cached_items, total=cached_total)

    # Controlled realtime lookup: rate limit + budget, then a single provider call.
    rate_limiter.check("search", settings.search_rate_limit_per_minute)
    if usage_repo.budget_exceeded(
        session,
        daily_budget=settings.daily_budget_usd,
        monthly_budget=settings.monthly_budget_usd,
    ):
        raise QuotaExceeded()

    try:
        provider = provider or get_provider()
        result = await provider.search_accounts(keyword, page=1, page_size=25)
    except DataSourceUnavailable:
        if total > 0:
            return SearchResult(items=items, total=total, degraded=True)
        raise

    stored_ids: list[int] = []
    for account in result.items:
        persisted = accounts_repo.upsert_from_provider(session, account)
        stored_ids.append(persisted.id)

    search_cache_repo.store(session, getattr(provider, "name", provider_name), keyword, stored_ids)

    usage_repo.log_usage(
        session,
        provider=getattr(provider, "name", "unknown"),
        endpoint="search_accounts",
        success=True,
        returned_items=len(result.items),
    )

    items, total = accounts_repo.search_local(session, keyword, page, page_size)
    return SearchResult(items=items, total=total)


def _items_from_ids(
    session: Session, account_ids: list[int], page: int, page_size: int
) -> tuple[list[WechatAccount], int]:
    """Rebuild a cached result page, preserving provider ordering."""
    if not account_ids:
        return [], 0
    found = {
        account.id: account
        for account in session.scalars(
            select(WechatAccount).where(WechatAccount.id.in_(account_ids))
        )
    }
    ordered = [found[i] for i in account_ids if i in found]
    start = (page - 1) * page_size
    return ordered[start : start + page_size], len(ordered)


def get_account(session: Session, account_id: int) -> WechatAccount | None:
    return accounts_repo.get_by_id(session, account_id)
