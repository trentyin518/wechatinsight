"""Qovia provider adapter (real API: https://api.qovia.ai).

WeChat endpoints (GET, query params, documented at qovia.ai/zh/docs/api-reference):
- ``/v1/raw/wechat/account_search`` (keyword, kind)  -> accounts (mp_id is stable)
- ``/v1/raw/wechat/articles``       (mp_id, cursor)   -> articles + has_more/cursor
- ``/v1/raw/wechat/article_metrics``(url)             -> reads/likes/watching/comments/shares
- ``/v1/raw/wechat/channel_search``                   -> video-channel accounts (not used by MVP)

All failures are translated into domain errors; raw vendor bodies and the API
key are never leaked. ``meta.charged_usd`` reflects real billing per call.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx

from app.core.errors import (
    DataSourceBillingError,
    DataSourceRateLimited,
    DataSourceUnavailable,
    ProviderError,
)
from app.providers.base import (
    ArticlePage,
    ProviderAccount,
    ProviderArticle,
    ProviderMetrics,
    SearchPage,
)


def _parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class QoviaProvider:
    name = "qovia"
    supports_metrics = True

    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 20.0,
        max_retries: int = 2,
        backoff: float = 0.3,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff = backoff

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        url = f"{self._base_url}{path}"
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        owns_client = self._client is None
        try:
            for attempt in range(self._max_retries + 1):
                try:
                    response = await client.get(url, params=params, headers=headers)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._backoff * (2**attempt))
                        continue
                    raise DataSourceUnavailable() from exc

                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise ProviderError() from exc
                if response.status_code == 401:
                    raise ProviderError("数据源鉴权失败。", code="DATA_SOURCE_AUTH")
                if response.status_code == 402:
                    raise DataSourceBillingError()
                if response.status_code == 403:
                    raise ProviderError("数据源无权限访问该接口。", code="DATA_SOURCE_SCOPE_DENIED")
                if response.status_code == 404:
                    raise ProviderError("数据源中不存在该数据。", code="NOT_FOUND")
                if response.status_code == 429:
                    raise DataSourceRateLimited()
                if response.status_code >= 500:
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._backoff * (2**attempt))
                        continue
                    raise DataSourceUnavailable()
                raise ProviderError("数据源请求被拒绝。", code="DATA_SOURCE_BAD_REQUEST")
        finally:
            if owns_client:
                await client.aclose()
        raise DataSourceUnavailable()

    # --- mapping ---------------------------------------------------------
    def _map_account(self, item: dict[str, Any]) -> ProviderAccount:
        verified = item.get("verified")
        return ProviderAccount(
            provider=self.name,
            provider_account_id=str(item.get("mp_id") or item.get("id") or ""),
            name=str(item.get("name") or ""),
            wechat_id=item.get("wechat_id"),
            avatar_url=item.get("avatar"),
            description=item.get("description"),
            verification_subject=item.get("verified_by") if verified else None,
            account_type=item.get("type"),
        )

    def _map_article(self, item: dict[str, Any]) -> ProviderArticle:
        return ProviderArticle(
            provider=self.name,
            provider_article_id=str(item["id"]) if item.get("id") is not None else None,
            title=str(item.get("title") or ""),
            url=str(item.get("url") or ""),
            published_at=_parse_dt(item.get("published_at")),
            cover_url=item.get("cover"),
            summary=item.get("digest"),
            author=item.get("author"),
            is_original=item.get("is_original"),
            is_paid=item.get("is_paid"),
        )

    def _map_metrics(self, data: dict[str, Any]) -> ProviderMetrics:
        return ProviderMetrics(
            provider=self.name,
            read_count=_as_int(data.get("reads")),
            like_count=_as_int(data.get("likes")),
            wow_count=_as_int(data.get("watching")),
            comment_count=_as_int(data.get("comments")),
            share_count=_as_int(data.get("shares")),
            raw_updated_at=_parse_dt(data.get("updated_at")),
        )

    # --- protocol --------------------------------------------------------
    async def search_accounts(
        self, keyword: str, page: int = 1, page_size: int = 20
    ) -> SearchPage:
        payload = await self._get(
            "/v1/raw/wechat/account_search",
            {"keyword": keyword, "kind": "all"},
        )
        data = payload.get("data") or {}
        items = [self._map_account(item) for item in data.get("items") or []]
        # This endpoint returns a single result set (no cursor param documented).
        return SearchPage(items=items, next_cursor=None)

    async def get_account(self, provider_account_id: str) -> ProviderAccount | None:
        # No account-profile endpoint; existing profile data is left untouched.
        return None

    async def get_articles(
        self,
        provider_account_id: str,
        cursor: str | None = None,
        page_size: int = 20,
        *,
        account_name: str | None = None,
    ) -> ArticlePage:
        params: dict[str, Any] = {"mp_id": provider_account_id}
        if cursor:
            params["cursor"] = cursor
        payload = await self._get("/v1/raw/wechat/articles", params)
        data = payload.get("data") or {}
        items = [self._map_article(item) for item in data.get("items") or []]
        next_cursor = data.get("cursor") if data.get("has_more") else None
        return ArticlePage(items=items, next_cursor=next_cursor)

    async def get_article_metrics(self, article_url: str) -> ProviderMetrics | None:
        try:
            payload = await self._get(
                "/v1/raw/wechat/article_metrics", {"url": article_url}
            )
        except ProviderError as exc:
            if exc.code == "NOT_FOUND":
                return None
            raise
        data = payload.get("data")
        if not isinstance(data, dict) or not data:
            return None
        return self._map_metrics(data)
