"""search cache

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-11

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _pk() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer, "sqlite")


def _ts() -> sa.types.TypeEngine:
    return sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "search_cache",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("keyword", sa.String(length=200), nullable=False),
        sa.Column("account_ids", sa.JSON(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fetched_at", _ts(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "keyword", name="uq_search_cache_provider_keyword"),
    )
    op.create_index("idx_search_cache_fetched_at", "search_cache", ["fetched_at"])


def downgrade() -> None:
    op.drop_index("idx_search_cache_fetched_at", table_name="search_cache")
    op.drop_table("search_cache")
