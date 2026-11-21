"""Account query service: local-first search with controlled cold start."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import DataSourceBusy, DataSourceUnavailable, QuotaExceeded
from app.db.models import WechatAccount
from app.providers.base import ProviderAccount, WeChatProvider
from app.providers.registry import get_provider
from app.repositories import accounts as accounts_repo
from app.repositories import search_cache as search_cache_repo
from app.repositories import search_retry_queue as search_retry_repo
from app.repositories import usage as usage_repo
from app.repositories.accounts import AccountFilters
from app.services import collection as collection_service
from app.services.ratelimit import rate_limiter

logger = logging.getLogger("wechat_insight.search")


class _AccountSearchBreaker:
    """Short-TTL circuit breaker for the billed account-search endpoint.

    With some plans this endpoint returns empty for *every* keyword yet still
    bills per call. After ``threshold`` consecutive empty results we short-
    circuit the paid call for ``cooldown`` seconds (then allow one probe). A
    non-empty result closes the breaker immediately.
    """

    def __init__(self) -> None:
        self._empty_streak = 0
        self._open_until = 0.0

    def should_skip(self) -> bool:
        return time.time() < self._open_until

    def record(self, had_items: bool, *, threshold: int, cooldown_seconds: int) -> None:
        if had_items:
            self._empty_streak = 0
            self._open_until = 0.0
            return
        self._empty_streak += 1
        if threshold > 0 and self._empty_streak >= threshold:
            self._open_until = time.time() + max(cooldown_seconds, 0)

    def reset(self) -> None:
        self._empty_streak = 0
        self._open_until = 0.0


_account_search_breaker = _AccountSearchBreaker()


def reset_account_search_breaker() -> None:
    _account_search_breaker.reset()


@dataclass(slots=True)
class SearchResult:
    items: list[WechatAccount]
    total: int
    degraded: bool = False
    # "local" = stored accounts; "content" = accounts derived from live content
    # search authors (no account-name match, but the account published matching
    # articles). Lets the UI label these honestly.
    source: str = "local"


def _has_filters(filters: AccountFilters | None) -> bool:
    """True when any constraint is set (an all-None object means "no filters")."""
    if filters is None:
        return False
    return any(getattr(filters, field) is not None for field in filters.__dataclass_fields__)


def _enqueue_visible_page(
    session: Session,
    items: list[WechatAccount],
    settings: Settings,
) -> None:
    """Schedule enrichment only for accounts rendered on this result page."""
    if not items or not settings.on_demand_sync_enabled:
        return
    try:
        # Savepoint so a scheduling hiccup rolls back only the new jobs and
        # never discards the accounts/cache work done earlier in this request.
        with session.begin_nested():
            collection_service.enqueue_accounts_for_sync(session, items, settings=settings)
    except Exception:
        # Enrichment is best-effort and must never make a search fail.
        logger.exception("failed to enqueue on-demand account enrichment")


async def _derive_accounts_from_content(
    session: Session,
    keyword: str,
    provider: WeChatProvider,
    settings: Settings,
) -> list[WechatAccount]:
    """Derive 公众号 from live content-search authors when account search is empty.

    The account-search endpoint indexes account *names*; content keywords (e.g. a
    newspaper's name appearing in article bodies) don't match it. ``/v1/search``
    does find the articles, whose ``author`` is the publishing 公众号 — so we
    upsert those as lightweight accounts so the 账号 view isn't empty.
    """
    from app.services import articles as articles_service

    if not settings.content_search_live_enabled:
        return []
    provider_name = getattr(provider, "name", "unknown")
    articles = await articles_service.search_external_articles(
        session, keyword, provider=provider, settings=settings
    )
    derived: list[WechatAccount] = []
    seen: set[str] = set()
    for article in articles:
        name = (article.author or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        derived.append(
            accounts_repo.upsert_from_provider(
                session,
                ProviderAccount(
                    provider=provider_name,
                    provider_account_id=f"content:{name}",
                    name=name,
                    avatar_url=article.author_avatar_url,
                ),
            )
        )
    return derived


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
        # Local hit (or a filter-only browse): these are real, already-known
        # accounts. Enrich just the page the user is looking at — page 2 of a
        # search enriches page 2's accounts, not everything at once.
        _enqueue_visible_page(session, items, settings)
        return SearchResult(items=items, total=total)

    if not settings.allow_cold_start_search:
        _enqueue_visible_page(session, items, settings)
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
            _enqueue_visible_page(session, cached_items, settings)
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

    provider = provider or get_provider()

    # The account-search endpoint is billed per call and is often empty for
    # content-style keywords. After a short streak of empties, short-circuit the
    # paid call (breaker) and fall straight through to content derivation.
    account_items: list[ProviderAccount] = []
    if not _account_search_breaker.should_skip():
        try:
            result = await provider.search_accounts(keyword, page=1, page_size=25)
            account_items = result.items
        except (DataSourceBusy, DataSourceUnavailable) as exc:
            # Upstream is sick. Serve any earlier (even expired) cached hits as a
            # graceful degradation so the user still sees known results.
            if not _has_filters(filters):
                stale = search_cache_repo.get(session, provider_name, keyword)
                if stale is not None and stale.total > 0:
                    cached_items, cached_total = _items_from_ids(
                        session, stale.account_ids, page, page_size
                    )
                    _enqueue_visible_page(session, cached_items, settings)
                    return SearchResult(items=cached_items, total=cached_total, degraded=True)
                # On "busy", queue a durable background retry so the next search
                # can be answered from the local store once upstream recovers.
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
                _enqueue_visible_page(session, items, settings)
                return SearchResult(items=items, total=total, degraded=True)
            raise
        _account_search_breaker.record(
            bool(account_items),
            threshold=settings.account_search_breaker_threshold,
            cooldown_seconds=settings.account_search_breaker_cooldown_seconds,
        )

    # Account-name search found nothing. A content keyword (e.g. a newspaper name
    # that only appears inside articles) still matches via /v1/search — derive
    # the publishing 公众号 from those authors so the account view isn't empty.
    if not account_items:
        derived = await _derive_accounts_from_content(session, keyword, provider, settings)
        if derived:
            return SearchResult(items=derived, total=len(derived), source="content")

    stored_ids: list[int] = []
    for account in account_items:
        persisted = accounts_repo.upsert_from_provider(session, account)
        stored_ids.append(persisted.id)

    search_cache_repo.store(session, getattr(provider, "name", provider_name), keyword, stored_ids)

    usage_repo.log_usage(
        session,
        provider=getattr(provider, "name", "unknown"),
        endpoint="search_accounts",
        success=True,
        returned_items=len(account_items),
    )

    items, total = accounts_repo.search_local(session, keyword, page, page_size, filters)
    _enqueue_visible_page(session, items, settings)
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
