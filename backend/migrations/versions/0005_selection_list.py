"""selection list (选号清单)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-15

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _pk() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer, "sqlite")


def _ts() -> sa.types.TypeEngine:
    return sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "selection_items",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("user_id", _pk(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("account_id", _pk(), sa.ForeignKey("wechat_accounts.id"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", _ts(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "account_id", name="uq_selection_user_account"),
    )
    op.create_index("idx_selection_user", "selection_items", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_selection_user", table_name="selection_items")
    op.drop_table("selection_items")
