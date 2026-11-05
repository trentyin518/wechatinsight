"""Account query service: local-first search with controlled cold start."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import DataSourceUnavailable, QuotaExceeded
from app.db.models import WechatAccount
from app.providers.base import WeChatProvider
from app.providers.registry import get_provider
from app.repositories import accounts as accounts_repo
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

    for account in result.items:
        accounts_repo.upsert_from_provider(session, account)

    usage_repo.log_usage(
        session,
        provider=getattr(provider, "name", "unknown"),
        endpoint="search_accounts",
        success=True,
        returned_items=len(result.items),
    )

    items, total = accounts_repo.search_local(session, keyword, page, page_size)
    return SearchResult(items=items, total=total)


def get_account(session: Session, account_id: int) -> WechatAccount | None:
    return accounts_repo.get_by_id(session, account_id)
