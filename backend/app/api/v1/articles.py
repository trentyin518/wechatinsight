"""Article + metrics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_approved
from app.core.errors import NotFoundError
from app.db.models import ArticleMetric, User
from app.repositories import articles as articles_repo
from app.schemas.articles import (
    ArticleDetail,
    ArticleSearchItem,
    ArticleSearchResponse,
    MetricPoint,
    MetricsHistoryResponse,
    ObservedChange,
)
from app.services import articles as articles_service

router = APIRouter(tags=["articles"])


def _metric_point(metric: ArticleMetric) -> MetricPoint:
    return MetricPoint(
        read_count=metric.read_count,
        like_count=metric.like_count,
        wow_count=metric.wow_count,
        comment_count=metric.comment_count,
        share_count=metric.share_count,
        observed_at=metric.observed_at,
        raw_updated_at=metric.raw_updated_at,
        provider=metric.provider,
    )


@router.get("/articles", response_model=ArticleSearchResponse)
async def search_articles(
    q: str = Query("", description="关键词"),
    scope: str = Query("title", pattern="^(title|title_content|topic|comment)$"),
    category: str | None = Query(None, description="所属行业"),
    original: bool | None = Query(None, description="文章属性：true=原创，false=非原创"),
    dedup: bool = Query(False, description="账号去重"),
    sort: str = Query("default", description="排序：default/latest/read/like/share/wow/comment"),
    time_days: int = Query(0, ge=0, description="发布时间范围（天，0=全部）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_db),
    _user: User | None = Depends(require_approved),
) -> ArticleSearchResponse:
    rows, total = articles_repo.search_articles(
        session,
        keyword=q,
        scope=scope,
        category=(category or None),
        original=original,
        dedup=dedup,
        sort=sort,
        time_days=time_days,
        page=page,
        page_size=page_size,
    )
    items = []
    for article, metric in rows:
        account = article.account
        items.append(
            ArticleSearchItem(
                id=article.id,
                title=article.title,
                article_url=article.article_url,
                provider=article.provider,
                published_at=article.published_at,
                is_original=article.is_original,
                author=article.author,
                ip_region=article.ip_region,
                summary=article.summary,
                account_id=article.account_id,
                account_name=account.name if account else "",
                account_avatar_url=account.avatar_url if account else None,
                account_category=account.category if account else None,
                account_estimated_fans=account.estimated_fans if account else None,
                read_count=metric.read_count if metric else None,
                like_count=metric.like_count if metric else None,
                share_count=metric.share_count if metric else None,
                wow_count=metric.wow_count if metric else None,
                comment_count=metric.comment_count if metric else None,
                metrics_observed_at=metric.observed_at if metric else None,
            )
        )

    # No collected articles matched: fall back to live content search so a
    # keyword that matches articles (but nothing we've collected) isn't empty.
    source = "local"
    if not items and q.strip():
        external = await articles_service.search_external_articles(session, q)
        if external:
            items = [
                ArticleSearchItem(
                    id=-(idx + 1),  # negative id signals "external / not stored"
                    title=p.title,
                    article_url=p.url,
                    provider=p.provider,
                    published_at=p.published_at,
                    is_original=p.is_original,
                    author=p.author,
                    ip_region=p.ip_region,
                    summary=p.summary,
                    account_id=0,
                    account_name=p.author or "—",
                    account_avatar_url=p.author_avatar_url,
                    external=True,
                )
                for idx, p in enumerate(external)
            ]
            total = len(items)
            source = "live"

    return ArticleSearchResponse(
        items=items,
        page=page if source == "local" else 1,
        page_size=page_size,
        total=total,
        source=source,
    )


@router.get("/articles/{article_id}", response_model=ArticleDetail)
def get_article(
    article_id: int,
    session: Session = Depends(get_db),
    _user: User | None = Depends(require_approved),
) -> ArticleDetail:
    found = articles_service.get_article(session, article_id)
    if found is None:
        raise NotFoundError("文章不存在。")
    article, metric = found
    return ArticleDetail(
        id=article.id,
        account_id=article.account_id,
        title=article.title,
        article_url=article.article_url,
        provider=article.provider,
        summary=article.summary,
        author=article.author,
        ip_region=article.ip_region,
        cover_url=article.cover_url,
        published_at=article.published_at,
        is_original=article.is_original,
        is_paid=article.is_paid,
        metrics=_metric_point(metric) if metric else None,
    )


@router.get("/articles/{article_id}/metrics", response_model=MetricsHistoryResponse)
def get_article_metrics(
    article_id: int,
    session: Session = Depends(get_db),
    _user: User | None = Depends(require_approved),
) -> MetricsHistoryResponse:
    if articles_repo.get_by_id(session, article_id) is None:
        raise NotFoundError("文章不存在。")
    points, (delta, rate) = articles_service.metrics_history(session, article_id)
    return MetricsHistoryResponse(
        article_id=article_id,
        points=[_metric_point(p) for p in points],
        observed_read_change=ObservedChange(delta=delta, rate=rate),
    )
