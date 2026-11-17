"""account attributes for filtering

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-15

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_NEW_COLUMNS = (
    ("category", sa.Text()),
    ("region", sa.Text()),
    ("estimated_fans", sa.Integer()),
    ("avg_read", sa.Integer()),
    ("avg_like", sa.Integer()),
    ("avg_wow", sa.Integer()),
    ("avg_share", sa.Integer()),
    ("avg_comment", sa.Integer()),
    ("article_count", sa.Integer()),
    ("estimated_price", sa.Integer()),
    ("ad_count_30d", sa.Integer()),
    ("xigua_index", sa.Float()),
    ("is_original", sa.Boolean()),
    ("has_video", sa.Boolean()),
)


def upgrade() -> None:
    for name, type_ in _NEW_COLUMNS:
        op.add_column("wechat_accounts", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _type in reversed(_NEW_COLUMNS):
        with op.batch_alter_table("wechat_accounts") as batch:
            batch.drop_column(name)
