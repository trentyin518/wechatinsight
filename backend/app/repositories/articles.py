"""Article + metric-snapshot persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ArticleMetric, WechatArticle
from app.db.url_utils import normalize_article_url
from app.providers.base import ProviderArticle, ProviderMetrics


def get_by_id(session: Session, article_id: int) -> WechatArticle | None:
    return session.get(WechatArticle, article_id)


def list_by_account(
    session: Session, account_id: int, page: int, page_size: int
) -> tuple[list[WechatArticle], int]:
    total = (
        session.scalar(
            select(func.count(WechatArticle.id)).where(WechatArticle.account_id == account_id)
        )
        or 0
    )
    stmt = (
        select(WechatArticle)
        .where(WechatArticle.account_id == account_id)
        .order_by(WechatArticle.published_at.desc().nullslast(), WechatArticle.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(session.scalars(stmt)), total


def latest_metric_map(session: Session, article_ids: list[int]) -> dict[int, ArticleMetric]:
    if not article_ids:
        return {}
    rn = (
        func.row_number()
        .over(
            partition_by=ArticleMetric.article_id,
            order_by=(ArticleMetric.observed_at.desc(), ArticleMetric.id.desc()),
        )
        .label("rn")
    )
    ranked = select(ArticleMetric.id.label("id"), rn).subquery()
    stmt = (
        select(ArticleMetric)
        .join(ranked, ArticleMetric.id == ranked.c.id)
        .where(ranked.c.rn == 1, ArticleMetric.article_id.in_(article_ids))
    )
    rows = session.scalars(stmt).all()
    return {row.article_id: row for row in rows}


def upsert_from_provider(
    session: Session, account_id: int, data: ProviderArticle
) -> WechatArticle:
    normalized = normalize_article_url(data.url)
    article = session.scalar(
        select(WechatArticle).where(
            WechatArticle.provider == data.provider,
            WechatArticle.normalized_url == normalized,
        )
    )
    if article is None:
        article = WechatArticle(
            account_id=account_id,
            provider=data.provider,
            provider_article_id=data.provider_article_id,
            title=data.title,
            article_url=data.url,
            normalized_url=normalized,
            summary=data.summary,
            author=data.author,
            cover_url=data.cover_url,
            published_at=data.published_at,
            is_original=data.is_original,
            is_paid=data.is_paid,
        )
        session.add(article)
    else:
        # Refresh optional fields when provided; keep earliest account binding.
        if data.title:
            article.title = data.title
        if data.provider_article_id:
            article.provider_article_id = data.provider_article_id
        for attr in ("summary", "author", "cover_url", "published_at", "is_original", "is_paid"):
            value = getattr(data, attr)
            if value is not None:
                setattr(article, attr, value)
    session.flush()
    return article


def add_metric_snapshot(
    session: Session, article_id: int, data: ProviderMetrics, *, observed_at: datetime | None = None
) -> ArticleMetric:
    """Append a new metric snapshot. Never overwrites previous observations."""
    metric = ArticleMetric(
        article_id=article_id,
        provider=data.provider,
        read_count=data.read_count,
        like_count=data.like_count,
        wow_count=data.wow_count,
        comment_count=data.comment_count,
        share_count=data.share_count,
        raw_updated_at=data.raw_updated_at,
    )
    if observed_at is not None:
        metric.observed_at = observed_at
    session.add(metric)
    session.flush()
    return metric


def list_metrics(session: Session, article_id: int) -> list[ArticleMetric]:
    stmt = (
        select(ArticleMetric)
        .where(ArticleMetric.article_id == article_id)
        .order_by(ArticleMetric.observed_at.asc(), ArticleMetric.id.asc())
    )
    return list(session.scalars(stmt))


def observed_read_change(
    metrics: list[ArticleMetric],
) -> tuple[int | None, float | None]:
    """Change between the last two valid read observations.

    Returns ``(delta, rate)``. ``rate`` is ``None`` when the previous value is
    missing or zero. ``delta`` is ``None`` when fewer than two valid readings.
    """
    valid = [m.read_count for m in metrics if m.read_count is not None]
    if len(valid) < 2:
        return None, None
    previous, current = valid[-2], valid[-1]
    delta = current - previous
    rate = (delta / previous * 100.0) if previous else None
    return delta, rate
