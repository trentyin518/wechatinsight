"""Article + metrics API schemas."""

from __future__ import annotations

from datetime import datetime

from app.schemas.common import ORMModel


class ArticleListItem(ORMModel):
    id: int
    title: str
    article_url: str
    provider: str
    published_at: datetime | None = None
    read_count: int | None = None
    like_count: int | None = None
    wow_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    metrics_observed_at: datetime | None = None


class ArticleListResponse(ORMModel):
    items: list[ArticleListItem]
    page: int
    page_size: int
    total: int


class MetricPoint(ORMModel):
    read_count: int | None = None
    like_count: int | None = None
    wow_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    observed_at: datetime
    raw_updated_at: datetime | None = None
    provider: str


class ObservedChange(ORMModel):
    delta: int | None = None
    rate: float | None = None


class MetricsHistoryResponse(ORMModel):
    article_id: int
    points: list[MetricPoint]
    observed_read_change: ObservedChange


class ArticleDetail(ORMModel):
    id: int
    account_id: int
    title: str
    article_url: str
    provider: str
    summary: str | None = None
    author: str | None = None
    cover_url: str | None = None
    published_at: datetime | None = None
    is_original: bool | None = None
    is_paid: bool | None = None
    metrics: MetricPoint | None = None
