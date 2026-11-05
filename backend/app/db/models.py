"""ORM models for the MVP data loop.

Design invariants (see design.md / specs):
- Internal primary keys; provider ids live in a mapping table.
- Metrics are append-only snapshots (never overwritten); ``null`` means unknown.
- Every row that comes from a third party keeps its ``provider`` for provenance.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import bigint_pk, timestamptz


class JobStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    RETRY = "RETRY"
    FAILED = "FAILED"

    ALL = {PENDING, RUNNING, SUCCESS, RETRY, FAILED}


class JobType:
    SYNC_ACCOUNT = "SYNC_ACCOUNT"
    SYNC_ARTICLES = "SYNC_ARTICLES"
    SYNC_METRICS = "SYNC_METRICS"


class Priority:
    A = "A"
    B = "B"
    C = "C"


class WechatAccount(Base):
    __tablename__ = "wechat_accounts"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    wechat_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(1), nullable=False, default=Priority.B)

    created_at: Mapped[datetime] = mapped_column(timestamptz(), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        timestamptz(), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(timestamptz(), nullable=True)

    articles: Mapped[list["WechatArticle"]] = relationship(back_populates="account")
    mappings: Mapped[list["ProviderAccountMapping"]] = relationship(back_populates="account")

    __table_args__ = (
        Index("idx_wechat_accounts_name", "name"),
        Index("idx_wechat_accounts_wechat_id", "wechat_id"),
    )


class ProviderAccountMapping(Base):
    __tablename__ = "provider_account_mappings"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("wechat_accounts.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(timestamptz(), server_default=func.now(), nullable=False)

    account: Mapped[WechatAccount] = relationship(back_populates="mappings")

    __table_args__ = (UniqueConstraint("provider", "provider_account_id", name="uq_provider_account"),)


class WechatArticle(Base):
    __tablename__ = "wechat_articles"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("wechat_accounts.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_article_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    article_url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    published_at: Mapped[datetime | None] = mapped_column(timestamptz(), nullable=True)
    is_original: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_paid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    created_at: Mapped[datetime] = mapped_column(timestamptz(), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        timestamptz(), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    account: Mapped[WechatAccount] = relationship(back_populates="articles")
    metrics: Mapped[list["ArticleMetric"]] = relationship(
        back_populates="article", order_by="ArticleMetric.observed_at"
    )

    __table_args__ = (
        UniqueConstraint("provider", "normalized_url", name="uq_article_provider_url"),
        Index("idx_articles_account_published", "account_id", "published_at"),
    )


class ArticleMetric(Base):
    __tablename__ = "article_metrics"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("wechat_articles.id"), nullable=False)

    provider: Mapped[str] = mapped_column(String(64), nullable=False)

    read_count: Mapped[int | None] = mapped_column(nullable=True)
    like_count: Mapped[int | None] = mapped_column(nullable=True)
    wow_count: Mapped[int | None] = mapped_column(nullable=True)
    comment_count: Mapped[int | None] = mapped_column(nullable=True)
    share_count: Mapped[int | None] = mapped_column(nullable=True)

    observed_at: Mapped[datetime] = mapped_column(timestamptz(), server_default=func.now(), nullable=False)
    raw_updated_at: Mapped[datetime | None] = mapped_column(timestamptz(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(timestamptz(), server_default=func.now(), nullable=False)

    article: Mapped[WechatArticle] = relationship(back_populates="metrics")

    __table_args__ = (Index("idx_article_metrics_article_time", "article_id", "observed_at"),)


class DataProvider(Base):
    __tablename__ = "data_providers"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(timestamptz(), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        timestamptz(), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[int | None] = mapped_column(nullable=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(1), nullable=False, default=Priority.B)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=JobStatus.PENDING)
    retry_count: Mapped[int] = mapped_column(nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(nullable=False, default=3)

    cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_calls: Mapped[int] = mapped_column(nullable=False, default=0)
    estimated_cost: Mapped[float] = mapped_column(nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(timestamptz(), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        timestamptz(), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(timestamptz(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(timestamptz(), nullable=True)

    __table_args__ = (
        Index("idx_sync_jobs_status_priority", "status", "priority"),
        Index("idx_sync_jobs_type_target", "job_type", "target_id"),
    )


class ApiUsageLog(Base):
    __tablename__ = "api_usage_logs"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    request_time: Mapped[datetime] = mapped_column(timestamptz(), server_default=func.now(), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    returned_items: Mapped[int] = mapped_column(nullable=False, default=0)
    request_units: Mapped[int] = mapped_column(nullable=False, default=1)
    estimated_cost: Mapped[float] = mapped_column(nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    job_id: Mapped[int | None] = mapped_column(ForeignKey("sync_jobs.id"), nullable=True)

    __table_args__ = (
        Index("idx_api_usage_provider_time", "provider", "request_time"),
    )
