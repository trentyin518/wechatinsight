"""search retry queue

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-17

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _pk() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer, "sqlite")


def _ts() -> sa.types.TypeEngine:
    return sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "search_retry_queue",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("keyword", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("next_retry_at", _ts(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", _ts(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", _ts(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "provider", "keyword", name="uq_search_retry_provider_keyword"
        ),
    )
    op.create_index(
        "idx_search_retry_status_next",
        "search_retry_queue",
        ["status", "next_retry_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_search_retry_status_next", table_name="search_retry_queue")
    op.drop_table("search_retry_queue")
