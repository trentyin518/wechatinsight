"""Xmedi (极媒数据) provider adapter — https://www.xmedi.cn/docs.

Base URL ``https://www.xmedi.cn/api/v1``; auth via ``X-XMEDI-Key`` header; every
call is ``POST`` JSON and returns ``{code, message, data, meta}`` where
``code == 0`` marks success (and billing). Failures are ``code != 0`` with a
stable ``error_code`` (``UNAUTHORIZED`` / ``INSUFFICIENT_BALANCE`` /
``RATE_LIMITED`` / ``NOT_FOUND`` / ``INTERNAL_ERROR`` / ``NOT_AVAILABLE`` …).

Endpoints used (WeChat):
- ``POST /wechat/search/accounts``     keyword → [{account_id, name}]        (¥0.15)
- ``POST /wechat/search/articles``     keyword → [{title, url}]               (¥0.15)
- ``POST /wechat/accounts/profile``    account_id → {account_id, name}        (¥0.15)
- ``POST /wechat/accounts/posts/list`` account_id → articles (+cursor)        (¥0.15)
- ``POST /wechat/articles/metrics/pro``url → read/like/comment/share/collect  (¥0.75)

Coverage caveats: Xmedi's WeChat search returns *minimal* rows (account_id+name
for accounts, title+url for articles — no author/avatar/ip), so those provider
fields stay ``None`` rather than being fabricated. ``metrics/pro`` has no
"在看"(wow) count, so ``wow_count`` is ``None``.
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


class XmediProvider:
    name = "xmedi"
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
        self._clients_by_loop: dict[asyncio.AbstractEventLoop, httpx.AsyncClient] = {}
        self._client_limits = httpx.Limits(
            max_connections=20, max_keepalive_connections=10
        )

    def _shared_client(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        for dead in [lp for lp in self._clients_by_loop if lp.is_closed()]:
            self._clients_by_loop.pop(dead, None)
        client = self._clients_by_loop.get(loop)
        if client is None:
            client = httpx.AsyncClient(timeout=self._timeout, limits=self._client_limits)
            self._clients_by_loop[loop] = client
        return client

    async def aclose(self) -> None:
        clients = list(self._clients_by_loop.values())
        self._clients_by_loop.clear()
        for client in clients:
            try:
                await client.aclose()
            except Exception:  # pragma: no cover - shutdown best-effort
                pass

    @staticmethod
    def _classify(status: int, payload: dict[str, Any]) -> ProviderError:
        err_code = str(payload.get("error_code") or "")
        if status == 401 or err_code == "UNAUTHORIZED":
            return ProviderError("数据源鉴权失败。", code="DATA_SOURCE_AUTH")
        if status == 402 or err_code == "INSUFFICIENT_BALANCE":
            return DataSourceBillingError()
        if status == 429 or err_code == "RATE_LIMITED":
            return DataSourceRateLimited()
        if status == 404 or err_code == "NOT_FOUND":
            return ProviderError("数据源中不存在该数据。", code="NOT_FOUND")
        if status == 503 or err_code == "NOT_AVAILABLE":
            return DataSourceBusy()
        if status == 400 or err_code == "VALIDATION_ERROR":
            return ProviderError("数据源请求被拒绝。", code="DATA_SOURCE_BAD_REQUEST")
        if status >= 500:
            return DataSourceUnavailable()
        return ProviderError("数据源请求被拒绝。", code="DATA_SOURCE_BAD_REQUEST")

    async def _request(
        self, path: str, *, body: dict[str, Any] | None = None, method: str = "POST"
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["X-XMEDI-Key"] = self._api_key
        url = f"{self._base_url}{path}"
        client = self._client if self._client is not None else self._shared_client()
        for attempt in range(self._max_retries + 1):
            try:
                if method == "GET":
                    response = await client.get(url, headers=headers)
                else:
                    response = await client.post(url, json=body or {}, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._backoff * (2**attempt))
                    continue
                raise DataSourceUnavailable() from exc

            try:
                payload = response.json()
            except ValueError:
                payload = None
            payload = payload if isinstance(payload, dict) else {}

            if response.status_code == 200 and payload.get("code") == 0:
                data = payload.get("data")
                return data if isinstance(data, dict) else {}

            # Transient server errors (except explicit "not available") retry.
            if (
                response.status_code in (500, 502, 504)
                and attempt < self._max_retries
            ):
                await asyncio.sleep(self._backoff * (2**attempt))
                continue
            raise self._classify(response.status_code, payload)
        raise DataSourceUnavailable()

    # --- mapping ---------------------------------------------------------
    def _map_account(self, item: dict[str, Any]) -> ProviderAccount:
        return ProviderAccount(
            provider=self.name,
            provider_account_id=str(item.get("account_id") or ""),
            name=_clean_text(item.get("name")) or "",
        )

    def _map_article(self, item: dict[str, Any]) -> ProviderArticle:
        return ProviderArticle(
            provider=self.name,
            provider_article_id=(
                str(item["app_msg_id"]) if item.get("app_msg_id") is not None else None
            ),
            title=_clean_text(item.get("title")) or "",
            url=str(item.get("url") or ""),
            published_at=_parse_dt(item.get("publish_time")),
            cover_url=item.get("cover"),
            summary=_clean_text(item.get("digest")),
        )

    # --- protocol --------------------------------------------------------
    async def search_accounts(
        self, keyword: str, page: int = 1, page_size: int = 20
    ) -> SearchPage:
        data = await self._request(
            "/wechat/search/accounts",
            body={"keyword": keyword, "page": page, "page_size": page_size},
        )
        items = [self._map_account(item) for item in data.get("items") or []]
        next_cursor = data.get("next_cursor") if data.get("has_more") else None
        return SearchPage(items=items, next_cursor=next_cursor)

    async def get_account(self, provider_account_id: str) -> ProviderAccount | None:
        try:
            data = await self._request(
                "/wechat/accounts/profile", body={"account_id": provider_account_id}
            )
        except ProviderError as exc:
            if exc.code == "NOT_FOUND":
                return None
            raise
        if not data:
            return None
        return ProviderAccount(
            provider=self.name,
            provider_account_id=str(data.get("account_id") or provider_account_id),
            name=_clean_text(data.get("name")) or "",
        )

    async def get_articles(
        self,
        provider_account_id: str,
        cursor: str | None = None,
        page_size: int = 20,
        *,
        account_name: str | None = None,
    ) -> ArticlePage:
        body: dict[str, Any] = {
            "account_id": provider_account_id,
            "page_size": page_size,
        }
        if cursor:
            body["cursor"] = cursor
        data = await self._request("/wechat/accounts/posts/list", body=body)
        items = [self._map_article(item) for item in data.get("items") or []]
        next_cursor = data.get("next_cursor") if data.get("has_more") else None
        return ArticlePage(items=items, next_cursor=next_cursor)

    async def get_article_metrics(self, article_url: str) -> ProviderMetrics | None:
        try:
            data = await self._request(
                "/wechat/articles/metrics/pro", body={"url": article_url}
            )
        except ProviderError as exc:
            if exc.code == "NOT_FOUND":
                return None
            raise
        if not isinstance(data, dict) or not data:
            return None
        return ProviderMetrics(
            provider=self.name,
            read_count=_as_int(data.get("read_num")),
            like_count=_as_int(data.get("like_num")),
            comment_count=_as_int(data.get("comment_num")),
            share_count=_as_int(data.get("share_num")),
            # Xmedi exposes no "在看"(wow) count.
            wow_count=None,
        )

    async def search_content(
        self, query: str, page_size: int = 20
    ) -> list[ProviderArticle]:
        data = await self._request(
            "/wechat/search/articles",
            body={"keyword": query, "page_size": page_size},
        )
        out: list[ProviderArticle] = []
        for item in data.get("items") or []:
            url = str(item.get("url") or "")
            if not url:
                continue
            out.append(
                ProviderArticle(
                    provider=self.name,
                    title=_clean_text(item.get("title")) or "",
                    url=url,
                )
            )
            if len(out) >= page_size:
                break
        return out

    async def get_billing(self) -> dict[str, Any] | None:
        """Account balance (best-effort; never raises)."""
        try:
            data = await self._request("/account/balance", method="GET")
        except Exception:
            return None
        return data if isinstance(data, dict) else None
