"""Unified provider interface + normalized data contract.

Business/API code depends only on :class:`WeChatProvider`. Concrete adapters
(e.g. ``qovia``) translate vendor payloads into these dataclasses. Missing data
is represented as ``None`` - never ``0`` - so provenance stays honest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class ProviderAccount:
    provider: str
    provider_account_id: str
    name: str
    wechat_id: str | None = None
    avatar_url: str | None = None
    description: str | None = None
    verification_subject: str | None = None
    account_type: str | None = None
    source_updated_at: datetime | None = None


@dataclass(slots=True)
class ProviderArticle:
    provider: str
    title: str
    url: str
    provider_article_id: str | None = None
    published_at: datetime | None = None
    cover_url: str | None = None
    summary: str | None = None
    author: str | None = None
    is_original: bool | None = None
    is_paid: bool | None = None


@dataclass(slots=True)
class ArticlePage:
    items: list[ProviderArticle] = field(default_factory=list)
    next_cursor: str | None = None


@dataclass(slots=True)
class ProviderMetrics:
    provider: str
    read_count: int | None = None
    like_count: int | None = None
    wow_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    observed_at: datetime = field(default_factory=utcnow)
    raw_updated_at: datetime | None = None


@dataclass(slots=True)
class SearchPage:
    items: list[ProviderAccount] = field(default_factory=list)
    next_cursor: str | None = None


@runtime_checkable
class WeChatProvider(Protocol):
    name: str

    async def search_accounts(
        self, keyword: str, page: int = 1, page_size: int = 20
    ) -> SearchPage: ...

    async def get_account(self, provider_account_id: str) -> ProviderAccount | None: ...

    async def get_articles(
        self,
        provider_account_id: str,
        cursor: str | None = None,
        page_size: int = 20,
        *,
        account_name: str | None = None,
    ) -> ArticlePage: ...

    async def get_article_metrics(self, article_url: str) -> ProviderMetrics | None: ...
