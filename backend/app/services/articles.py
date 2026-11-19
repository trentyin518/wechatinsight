"""Article query service."""

from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.models import ArticleMetric, WechatArticle
from app.providers.base import ProviderArticle, WeChatProvider
from app.providers.registry import get_provider
from app.repositories import articles as articles_repo
from app.repositories import usage as usage_repo
from app.services.ratelimit import rate_limiter

logger = logging.getLogger("wechat_insight.content_search")

# In-process short-TTL cache for live content search: repeated identical searches
# within the window are answered without paying the provider again.
_EXTERNAL_CACHE: dict[tuple[str, str], tuple[float, list[ProviderArticle]]] = {}
_EXTERNAL_CACHE_MAX = 512


def _cache_key(provider_name: str, keyword: str) -> tuple[str, str]:
    return (provider_name, keyword.strip().lower())


def _cache_get(
    provider_name: str, keyword: str, ttl_seconds: int
) -> list[ProviderArticle] | None:
    key = _cache_key(provider_name, keyword)
    hit = _EXTERNAL_CACHE.get(key)
    if hit is None:
        return None
    ts, items = hit
    if ttl_seconds <= 0 or (time.time() - ts) > ttl_seconds:
        _EXTERNAL_CACHE.pop(key, None)
        return None
    return items


def _cache_put(provider_name: str, keyword: str, items: list[ProviderArticle]) -> None:
    _EXTERNAL_CACHE[_cache_key(provider_name, keyword)] = (time.time(), items)
    if len(_EXTERNAL_CACHE) > _EXTERNAL_CACHE_MAX:
        oldest = min(_EXTERNAL_CACHE, key=lambda k: _EXTERNAL_CACHE[k][0])
        _EXTERNAL_CACHE.pop(oldest, None)


async def search_external_articles(
    session: Session,
    keyword: str,
    *,
    provider: WeChatProvider | None = None,
    settings: Settings | None = None,
) -> list[ProviderArticle]:
    """Live content search fallback (qovia ``/v1/search``).

    Guards: enabled flag → short cache → rate limit → budget. Never raises on a
    search failure — returns ``[]`` so the caller keeps its normal empty state
    rather than surfacing a provider error.
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return []

    settings = settings or get_settings()
    if not settings.content_search_live_enabled:
        return []

    provider = provider or get_provider()
    search_content = getattr(provider, "search_content", None)
    if not getattr(provider, "supports_content_search", False) or search_content is None:
        return []
    provider_name = getattr(provider, "name", "unknown")

    cached = _cache_get(provider_name, keyword, settings.content_search_cache_ttl_seconds)
    if cached is not None:
        return cached

    try:
        rate_limiter.check("content_search", settings.search_rate_limit_per_minute)
    except AppError:
        return []

    if usage_repo.budget_exceeded(
        session,
        daily_budget=settings.daily_budget_usd,
        monthly_budget=settings.monthly_budget_usd,
    ):
        return []

    try:
        items = await search_content(
            keyword, page_size=settings.content_search_page_size
        )
    except AppError as exc:
        logger.warning("content search failed: %s", getattr(exc, "code", exc))
        return []
    except Exception:
        logger.exception("content search crashed")
        return []

    usage_repo.log_usage(
        session,
        provider=provider_name,
        endpoint="search_content",
        success=True,
        returned_items=len(items),
    )
    _cache_put(provider_name, keyword, items)
    return items


def list_articles(
    session: Session, account_id: int, page: int, page_size: int
) -> tuple[list[tuple[WechatArticle, ArticleMetric | None]], int]:
    rows, total = articles_repo.list_by_account(session, account_id, page, page_size)
    latest = articles_repo.latest_metric_map(session, [r.id for r in rows])
    return [(row, latest.get(row.id)) for row in rows], total


def get_article(
    session: Session, article_id: int
) -> tuple[WechatArticle, ArticleMetric | None] | None:
    article = articles_repo.get_by_id(session, article_id)
    if article is None:
        return None
    latest = articles_repo.latest_metric_map(session, [article.id]).get(article.id)
    return article, latest


def metrics_history(
    session: Session, article_id: int
) -> tuple[list[ArticleMetric], tuple[int | None, float | None]]:
    points = articles_repo.list_metrics(session, article_id)
    change = articles_repo.observed_read_change(points)
    return points, change
