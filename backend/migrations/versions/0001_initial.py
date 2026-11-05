"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-02

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _pk() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer, "sqlite")


def _ts() -> sa.types.TypeEngine:
    return sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "wechat_accounts",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("wechat_id", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("verification_subject", sa.Text(), nullable=True),
        sa.Column("account_type", sa.Text(), nullable=True),
        sa.Column("primary_provider", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.String(length=1), nullable=False, server_default=sa.text("'B'")),
        sa.Column("created_at", _ts(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", _ts(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_synced_at", _ts(), nullable=True),
    )
    op.create_index("idx_wechat_accounts_name", "wechat_accounts", ["name"])
    op.create_index("idx_wechat_accounts_wechat_id", "wechat_accounts", ["wechat_id"])

    op.create_table(
        "provider_account_mappings",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("account_id", _pk(), sa.ForeignKey("wechat_accounts.id"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", _ts(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("provider", "provider_account_id", name="uq_provider_account"),
    )
    op.create_index(
        "ix_provider_account_mappings_account_id", "provider_account_mappings", ["account_id"]
    )

    op.create_table(
        "wechat_articles",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("account_id", _pk(), sa.ForeignKey("wechat_accounts.id"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_article_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("article_url", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("published_at", _ts(), nullable=True),
        sa.Column("is_original", sa.Boolean(), nullable=True),
        sa.Column("is_paid", sa.Boolean(), nullable=True),
        sa.Column("created_at", _ts(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", _ts(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("provider", "normalized_url", name="uq_article_provider_url"),
    )
    op.create_index(
        "idx_articles_account_published", "wechat_articles", ["account_id", "published_at"]
    )

    op.create_table(
        "article_metrics",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("article_id", _pk(), sa.ForeignKey("wechat_articles.id"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("read_count", sa.BigInteger(), nullable=True),
        sa.Column("like_count", sa.BigInteger(), nullable=True),
        sa.Column("wow_count", sa.BigInteger(), nullable=True),
        sa.Column("comment_count", sa.BigInteger(), nullable=True),
        sa.Column("share_count", sa.BigInteger(), nullable=True),
        sa.Column("observed_at", _ts(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("raw_updated_at", _ts(), nullable=True),
        sa.Column("created_at", _ts(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(
        "idx_article_metrics_article_time",
        "article_metrics",
        ["article_id", "observed_at"],
    )

    op.create_table(
        "data_providers",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False, unique=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", _ts(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", _ts(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "sync_jobs",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.String(length=1), nullable=False, server_default=sa.text("'B'")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("api_calls", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", _ts(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", _ts(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("started_at", _ts(), nullable=True),
        sa.Column("finished_at", _ts(), nullable=True),
    )
    op.create_index(
        "idx_sync_jobs_status_priority", "sync_jobs", ["status", "priority"]
    )
    op.create_index(
        "idx_sync_jobs_type_target", "sync_jobs", ["job_type", "target_id"]
    )

    op.create_table(
        "api_usage_logs",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=128), nullable=False),
        sa.Column(
            "request_time", _ts(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("returned_items", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("request_units", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("job_id", sa.BigInteger(), sa.ForeignKey("sync_jobs.id"), nullable=True),
    )
    op.create_index(
        "idx_api_usage_provider_time", "api_usage_logs", ["provider", "request_time"]
    )


def downgrade() -> None:
    op.drop_index("idx_api_usage_provider_time", table_name="api_usage_logs")
    op.drop_table("api_usage_logs")
    op.drop_index("idx_sync_jobs_type_target", table_name="sync_jobs")
    op.drop_index("idx_sync_jobs_status_priority", table_name="sync_jobs")
    op.drop_table("sync_jobs")
    op.drop_table("data_providers")
    op.drop_index("idx_article_metrics_article_time", table_name="article_metrics")
    op.drop_table("article_metrics")
    op.drop_index("idx_articles_account_published", table_name="wechat_articles")
    op.drop_table("wechat_articles")
    op.drop_index(
        "ix_provider_account_mappings_account_id", table_name="provider_account_mappings"
    )
    op.drop_table("provider_account_mappings")
    op.drop_index("idx_wechat_accounts_wechat_id", table_name="wechat_accounts")
    op.drop_index("idx_wechat_accounts_name", table_name="wechat_accounts")
    op.drop_table("wechat_accounts")
