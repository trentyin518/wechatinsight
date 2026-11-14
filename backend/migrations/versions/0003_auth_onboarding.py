"""auth + onboarding

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-13

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _pk() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer, "sqlite")


def _ts() -> sa.types.TypeEngine:
    return sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("wechat_unionid", sa.String(length=128), nullable=True),
        sa.Column("wechat_openid", sa.String(length=128), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("onboarding_status", sa.String(length=16), nullable=False, server_default="none"),
        sa.Column("created_at", _ts(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", _ts(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("phone", name="uq_users_phone"),
        sa.UniqueConstraint("wechat_unionid", name="uq_users_wechat_unionid"),
    )
    op.create_index("idx_users_phone", "users", ["phone"])
    op.create_index("idx_users_wechat_openid", "users", ["wechat_openid"])

    op.create_table(
        "user_sessions",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("user_id", _pk(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", _ts(), nullable=False),
        sa.Column("revoked_at", _ts(), nullable=True),
        sa.Column("created_at", _ts(), nullable=False, server_default=sa.func.now()),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
    )
    op.create_index("idx_user_sessions_user", "user_sessions", ["user_id"])

    op.create_table(
        "onboarding_proofs",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("user_id", _pk(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", _ts(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_onboarding_proofs_user", "onboarding_proofs", ["user_id"])

    op.create_table(
        "onboarding_submissions",
        sa.Column("id", _pk(), primary_key=True),
        sa.Column("user_id", _pk(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("source_channel", sa.String(length=32), nullable=True),
        sa.Column("source_other", sa.Text(), nullable=True),
        sa.Column("user_type", sa.String(length=32), nullable=True),
        sa.Column("user_type_other", sa.Text(), nullable=True),
        sa.Column("company_name", sa.Text(), nullable=True),
        sa.Column("contact_name", sa.Text(), nullable=True),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("needs", sa.Text(), nullable=True),
        sa.Column("proof_id", _pk(), sa.ForeignKey("onboarding_proofs.id"), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("reviewer_id", _pk(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("submitted_at", _ts(), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", _ts(), nullable=True),
    )
    op.create_index("idx_onboarding_submissions_user", "onboarding_submissions", ["user_id"])
    op.create_index("idx_onboarding_submissions_status", "onboarding_submissions", ["status"])


def downgrade() -> None:
    op.drop_index("idx_onboarding_submissions_status", table_name="onboarding_submissions")
    op.drop_index("idx_onboarding_submissions_user", table_name="onboarding_submissions")
    op.drop_table("onboarding_submissions")
    op.drop_index("idx_onboarding_proofs_user", table_name="onboarding_proofs")
    op.drop_table("onboarding_proofs")
    op.drop_index("idx_user_sessions_user", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("idx_users_wechat_openid", table_name="users")
    op.drop_index("idx_users_phone", table_name="users")
    op.drop_table("users")
