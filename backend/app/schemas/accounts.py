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
    verification_subject: str | None = None
    account_type: str | None = None
    provider: str
    last_synced_at: datetime | None = None
    category: str | None = None
    region: str | None = None
    estimated_fans: int | None = None
    avg_read: int | None = None
    avg_like: int | None = None
    avg_wow: int | None = None
    avg_share: int | None = None
    avg_comment: int | None = None
    article_count: int | None = None
    estimated_price: int | None = None
    ad_count_30d: int | None = None
    xigua_index: float | None = None
    is_original: bool | None = None
    has_video: bool | None = None


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
    category: str | None = None
    region: str | None = None
    estimated_fans: int | None = None
    avg_read: int | None = None
    avg_like: int | None = None
    avg_wow: int | None = None
    avg_share: int | None = None
    avg_comment: int | None = None
    article_count: int | None = None
    estimated_price: int | None = None
    ad_count_30d: int | None = None
    xigua_index: float | None = None
    is_original: bool | None = None
    has_video: bool | None = None


class AccountSearchResponse(ORMModel):
    items: list[AccountOut]
    page: int
    page_size: int
    total: int


class SimilarAccountsResponse(ORMModel):
    account: AccountOut
    items: list[AccountOut]
