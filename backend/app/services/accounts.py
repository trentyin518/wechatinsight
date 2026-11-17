"""Account query service: local-first search with controlled cold start."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import DataSourceBusy, DataSourceUnavailable, QuotaExceeded
from app.db.models import WechatAccount
from app.providers.base import WeChatProvider
from app.providers.registry import get_provider
from app.repositories import accounts as accounts_repo
from app.repositories import search_cache as search_cache_repo
from app.repositories import search_retry_queue as search_retry_repo
from app.repositories import usage as usage_repo
from app.repositories.accounts import AccountFilters
from app.services.ratelimit import rate_limiter


@dataclass(slots=True)
class SearchResult:
    items: list[WechatAccount]
    total: int
    degraded: bool = False


def _has_filters(filters: AccountFilters | None) -> bool:
    """True when any constraint is set (an all-None object means "no filters")."""
    if filters is None:
        return False
    return any(getattr(filters, field) is not None for field in filters.__dataclass_fields__)


async def search_accounts(
    session: Session,
    keyword: str,
    page: int,
    page_size: int,
    *,
    provider: WeChatProvider | None = None,
    settings: Settings | None = None,
    filters: AccountFilters | None = None,
    mode: str = "name",
) -> SearchResult:
    if mode == "article":
        items, total = accounts_repo.search_by_article_local(
            session, keyword, page, page_size, filters
        )
        return SearchResult(items=items, total=total)

    settings = settings or get_settings()
    items, total = accounts_repo.search_local(session, keyword, page, page_size, filters)
    if total > 0 or not (keyword or "").strip():
        return SearchResult(items=items, total=total)

    if not settings.allow_cold_start_search:
        return SearchResult(items=items, total=total)

    provider_name = getattr(provider, "name", None) or settings.default_provider

    # A keyword we already paid for — including one that returned nothing — is
    # answered from the cache. Skipped when filters are present so the cached
    # ordering cannot bypass the selected constraints.
    if not _has_filters(filters):
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
        # This is our own cost guard (DAILY/MONTHLY_BUDGET_USD), NOT an upstream
        # quota. Say so explicitly so it is not confused with the provider.
        raise QuotaExceeded(
            "今日/本月已达成本预算上限（成本保护），并非数据源额度不足；"
            "请稍后再试或调整 DAILY_BUDGET_USD / MONTHLY_BUDGET_USD。"
        )

    try:
        provider = provider or get_provider()
        result = await provider.search_accounts(keyword, page=1, page_size=25)
    except (DataSourceBusy, DataSourceUnavailable) as exc:
        # Upstream is sick. Serve any earlier (even expired) cached hits as a
        # graceful degradation so the user still sees known results.
        if not _has_filters(filters):
            stale = search_cache_repo.get(session, provider_name, keyword)
            if stale is not None and stale.total > 0:
                cached_items, cached_total = _items_from_ids(
                    session, stale.account_ids, page, page_size
                )
                return SearchResult(items=cached_items, total=cached_total, degraded=True)
            # On "busy", queue a durable background retry so the next search can
            # be answered from the local store once the upstream recovers.
            if isinstance(exc, DataSourceBusy):
                try:
                    search_retry_repo.enqueue(
                        session,
                        provider_name,
                        keyword,
                        max_attempts=settings.search_retry_max_attempts,
                    )
                    session.commit()
                except Exception:  # queueing must never mask the real error
                    session.rollback()
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

    items, total = accounts_repo.search_local(session, keyword, page, page_size, filters)
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
