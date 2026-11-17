"""wechat_articles.ip_region (文章 IP 属地)

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-15

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("wechat_articles") as batch:
        batch.add_column(sa.Column("ip_region", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("wechat_articles") as batch:
        batch.drop_column("ip_region")
