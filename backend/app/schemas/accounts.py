"""Account API schemas."""

from __future__ import annotations

from datetime import datetime

from app.schemas.common import ORMModel


class AccountOut(ORMModel):
    id: int
    name: str
    wechat_id: str | None = None
    description: str | None = None
    avatar_url: str | None = None
    provider: str
    last_synced_at: datetime | None = None


class AccountDetail(ORMModel):
    id: int
    name: str
    wechat_id: str | None = None
    description: str | None = None
    avatar_url: str | None = None
    verification_subject: str | None = None
    account_type: str | None = None
    provider: str
    created_at: datetime
    updated_at: datetime
    last_synced_at: datetime | None = None


class AccountSearchResponse(ORMModel):
    items: list[AccountOut]
    page: int
    page_size: int
    total: int
