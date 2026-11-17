"""Article + metric-snapshot persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import ArticleMetric, WechatAccount, WechatArticle
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


_METRIC_FIELDS = {
    "read": "read_count",
    "like": "like_count",
    "share": "share_count",
    "wow": "wow_count",
    "comment": "comment_count",
}


def search_articles(
    session: Session,
    *,
    keyword: str,
    scope: str,
    category: str | None,
    original: bool | None,
    dedup: bool,
    sort: str,
    time_days: int,
    page: int,
    page_size: int,
) -> tuple[list[tuple[WechatArticle, ArticleMetric | None]], int]:
    """Keyword search over collected articles.

    Matches on title (``scope=title``) or title+summary (other scopes). Sort,
    de-duplication and pagination are applied in Python over the filtered set,
    which is fine for the MVP dataset and keeps "missing" metrics from sorting
    incorrectly.
    """
    conditions = []
    kw = (keyword or "").strip()
    if kw:
        pattern = f"%{kw}%"
        if scope == "title":
            conditions.append(WechatArticle.title.ilike(pattern))
        else:
            conditions.append(
                or_(
                    WechatArticle.title.ilike(pattern),
                    WechatArticle.summary.ilike(pattern),
                )
            )

    stmt = select(WechatArticle).join(
        WechatAccount, WechatArticle.account_id == WechatAccount.id
    )
    if category:
        stmt = stmt.where(WechatAccount.category == category)
    if original is not None:
        stmt = stmt.where(WechatArticle.is_original.is_(original))
    if time_days and time_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=time_days)
        stmt = stmt.where(WechatArticle.published_at >= cutoff)
    if conditions:
        stmt = stmt.where(*conditions)

    articles = list(session.scalars(stmt))
    metric_map = latest_metric_map(session, [a.id for a in articles])
    rows: list[tuple[WechatArticle, ArticleMetric | None]] = [
        (a, metric_map.get(a.id)) for a in articles
    ]

    def pub_ts(article: WechatArticle) -> float:
        return article.published_at.timestamp() if article.published_at else 0.0

    if sort in _METRIC_FIELDS:
        field = _METRIC_FIELDS[sort]

        def metric_key(row: tuple[WechatArticle, ArticleMetric | None]) -> float:
            metric = row[1]
            value = getattr(metric, field) if metric else None
            return -1.0 if value is None else float(value)

        rows.sort(key=lambda r: (metric_key(r), pub_ts(r[0]), r[0].id), reverse=True)
    else:
        rows.sort(key=lambda r: (pub_ts(r[0]), r[0].id), reverse=True)

    if dedup:
        seen: set[int] = set()
        unique: list[tuple[WechatArticle, ArticleMetric | None]] = []
        for row in rows:
            if row[0].account_id in seen:
                continue
            seen.add(row[0].account_id)
            unique.append(row)
        rows = unique

    total = len(rows)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total


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
            ip_region=data.ip_region,
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
        for attr in (
            "summary",
            "author",
            "ip_region",
            "cover_url",
            "published_at",
            "is_original",
            "is_paid",
        ):
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
