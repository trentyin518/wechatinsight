"""Qovia provider adapter (real API: https://api.qovia.ai).

WeChat endpoints (GET, query params, documented at qovia.ai/zh/docs/api-reference):
- ``/v1/raw/wechat/account_search`` (keyword, kind)  -> accounts (mp_id is stable)
- ``/v1/raw/wechat/articles``       (mp_id, cursor)   -> articles + has_more/cursor
- ``/v1/raw/wechat/article_metrics``(url)             -> reads/likes/watching/comments/shares
- ``/v1/raw/wechat/channel_search``                   -> video-channel accounts (not used by MVP)

Field coverage per the docs:
- account_search returns id, mp_id, name, wechat_id, avatar, description,
  verified, verified_by, type — i.e. profile facts only.
- articles returns id, title, url, published_at, cover, digest, author,
  ip_region, is_original, is_paid, reads_label, likes (+ cursor/has_more).
- article_metrics returns reads, likes, watching, comments, shares, updated_at.

Qovia does NOT expose account-level commercial estimates (预估活跃粉丝、报价、
30天广告数、西瓜指数、所属行业、运营地区、头条平均阅读 etc.). Those provider
fields stay ``None`` rather than being fabricated, and derived aggregates
(发文篇数 / 平均阅读) can be computed from articles + metrics if needed.

All failures are translated into domain errors; raw vendor bodies and the API
key are never leaked. ``meta.charged_usd`` reflects real billing per call.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

import httpx

from app.core.errors import (
    DataSourceBillingError,
    DataSourceBusy,
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


def _is_upstream_busy(response: httpx.Response) -> bool:
    try:
        body = response.json()
    except ValueError:
        return False
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        code = str(err.get("code") or "")
        msg = str(err.get("message") or "")
        return "busy" in code or "busy" in msg
    return False


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"<[^>]*>", "", str(value))
    return text.strip() or None


class QoviaProvider:
    name = "qovia"
    supports_metrics = True
    supports_content_search = True

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
        # Reuse one persistent client per event loop so consecutive calls keep
        # their TCP/TLS connections (no handshake per call). Keyed by loop
        # because the worker runs each cycle in a fresh asyncio.run() loop.
        self._clients_by_loop: dict[asyncio.AbstractEventLoop, httpx.AsyncClient] = {}
        self._client_limits = httpx.Limits(
            max_connections=20, max_keepalive_connections=10
        )

    def _shared_client(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        # Drop clients whose loop has closed (worker: new loop each cycle) so the
        # cache can't grow unbounded across many scheduler ticks.
        for dead in [lp for lp in self._clients_by_loop if lp.is_closed()]:
            self._clients_by_loop.pop(dead, None)
        client = self._clients_by_loop.get(loop)
        if client is None:
            client = httpx.AsyncClient(timeout=self._timeout, limits=self._client_limits)
            self._clients_by_loop[loop] = client
        return client

    async def aclose(self) -> None:
        """Close every cached persistent client (best-effort, on shutdown)."""
        clients = list(self._clients_by_loop.values())
        self._clients_by_loop.clear()
        for client in clients:
            try:
                await client.aclose()
            except Exception:  # pragma: no cover - shutdown best-effort
                pass

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        url = f"{self._base_url}{path}"
        # Use the caller-provided client (tests) or a per-loop persistent client
        # (production: keep-alive across the batch). Neither is closed per call.
        client = self._client if self._client is not None else self._shared_client()
        for attempt in range(self._max_retries + 1):
            try:
                response = await client.request(
                    method, url, params=params, json=json_body, headers=headers
                )
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
                busy = _is_upstream_busy(response)
                if attempt < self._max_retries:
                    # Upstream "busy" bursts tend to last a little longer, so
                    # wait a bit more before retrying those.
                    delay = self._backoff * (2**attempt) * (3 if busy else 1)
                    await asyncio.sleep(delay)
                    continue
                raise DataSourceBusy() if busy else DataSourceUnavailable()
            raise ProviderError("数据源请求被拒绝。", code="DATA_SOURCE_BAD_REQUEST")
        raise DataSourceUnavailable()

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        return await self._request("GET", path, params=params)

    # --- mapping ---------------------------------------------------------
    def _map_account(self, item: dict[str, Any]) -> ProviderAccount:
        verified = item.get("verified")
        return ProviderAccount(
            provider=self.name,
            provider_account_id=str(item.get("mp_id") or item.get("id") or ""),
            name=_clean_text(item.get("name")) or "",
            wechat_id=item.get("wechat_id"),
            avatar_url=item.get("avatar"),
            description=_clean_text(item.get("description")),
            verification_subject=item.get("verified_by") if verified else None,
            account_type=item.get("type"),
        )

    def _map_article(self, item: dict[str, Any]) -> ProviderArticle:
        return ProviderArticle(
            provider=self.name,
            provider_article_id=str(item["id"]) if item.get("id") is not None else None,
            title=_clean_text(item.get("title")) or "",
            url=str(item.get("url") or ""),
            published_at=_parse_dt(item.get("published_at")),
            cover_url=item.get("cover"),
            summary=_clean_text(item.get("digest")),
            author=_clean_text(item.get("author")),
            ip_region=item.get("ip_region"),
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

    async def search_content(self, query: str, page_size: int = 20) -> list[ProviderArticle]:
        """Live content search across WeChat articles via ``POST /v1/search``.

        Returns articles (with author name/avatar) even when no account matches
        the keyword — the account-search endpoint is empty for content keywords.
        """
        payload = await self._request("POST", "/v1/search", json_body={"query": query})
        data = payload.get("data") or {}
        out: list[ProviderArticle] = []
        for item in data.get("items") or []:
            platform = str(item.get("platform") or "wechat").lower()
            if platform != "wechat":
                continue
            url = str(item.get("url") or "")
            if not url:
                continue
            author = item.get("author") or {}
            author = author if isinstance(author, dict) else {}
            item_type = item.get("type")
            out.append(
                ProviderArticle(
                    provider=self.name,
                    provider_article_id=(
                        str(item["id"]) if item.get("id") is not None else None
                    ),
                    title=_clean_text(item.get("title")) or "",
                    url=url,
                    published_at=_parse_dt(item.get("published_at")),
                    summary=_clean_text(item.get("text")) or _clean_text(item.get("summary")),
                    author=_clean_text(author.get("name")),
                    author_avatar_url=author.get("avatar"),
                    ip_region=item.get("ip_location"),
                    is_original=(
                        str(item_type).lower() == "original"
                        if item_type is not None
                        else None
                    ),
                )
            )
            if len(out) >= page_size:
                break
        return out

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

    async def get_billing(self) -> dict[str, Any] | None:
        """Account billing/balance info (best-effort; never raises)."""
        try:
            payload = await self._get("/v1/account", {})
        except Exception:
            return None
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return None
        billing = data.get("billing")
        return billing if isinstance(billing, dict) else None
