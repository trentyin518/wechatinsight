"""Article + metrics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_approved
from app.core.errors import NotFoundError
from app.db.models import ArticleMetric, User
from app.repositories import articles as articles_repo
from app.schemas.articles import (
    ArticleDetail,
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
