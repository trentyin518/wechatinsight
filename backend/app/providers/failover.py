"""Multi-source failover: try data sources in order, switch on failure.

Keyword-based calls (``search_accounts`` / ``search_content``) and URL-based
metrics (``get_article_metrics``) transparently fall through to the next
provider when one raises a provider/transport error, so a single vendor outage
never takes search down. Id-scoped lookups (``get_account`` / ``get_articles``)
use the primary provider only — their ids (``mp_id`` / ``gh_…``) are vendor
specific and are not portable across sources.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from app.core.errors import (
    DataSourceBillingError,
    DataSourceBusy,
    DataSourceRateLimited,
    DataSourceUnavailable,
    ProviderError,
    QuotaExceeded,
)
from app.providers.base import (
    ArticlePage,
    ProviderAccount,
    ProviderArticle,
    ProviderMetrics,
    SearchPage,
    WeChatProvider,
)

logger = logging.getLogger("wechat_insight.providers.failover")

# A provider "failed" (as opposed to legitimately returning no rows) when it
# raises one of these — switch to the next source.
_FAILOVER_ERRORS = (
    DataSourceUnavailable,
    DataSourceBusy,
    DataSourceBillingError,
    DataSourceRateLimited,
    QuotaExceeded,
    ProviderError,
)


class FailoverProvider:
    """Composite :class:`WeChatProvider` over an ordered provider list."""

    def __init__(self, providers: list[WeChatProvider]) -> None:
        if not providers:
            raise ValueError("FailoverProvider requires at least one provider")
        self._providers = list(providers)

    @property
    def providers(self) -> tuple[WeChatProvider, ...]:
        return tuple(self._providers)

    @property
    def name(self) -> str:
        # Label = primary source; individual rows still carry their own
        # ``provider`` provenance from whichever adapter served them.
        return self._providers[0].name

    @property
    def supports_metrics(self) -> bool:
        return any(getattr(p, "supports_metrics", True) for p in self._providers)

    @property
    def supports_content_search(self) -> bool:
        return any(
            getattr(p, "supports_content_search", False) for p in self._providers
        )

    async def _first_ok(
        self,
        method: str,
        *args: Any,
        capable: Callable[[WeChatProvider], bool] | None = None,
        **kwargs: Any,
    ) -> Any:
        last_exc: Exception | None = None
        for provider in self._providers:
            if capable is not None and not capable(provider):
                continue
            fn = getattr(provider, method, None)
            if fn is None:
                continue
            try:
                return await fn(*args, **kwargs)
            except _FAILOVER_ERRORS as exc:
                last_exc = exc
                logger.warning(
                    "provider %s failed on %s (%s); trying next source",
                    getattr(provider, "name", "?"),
                    method,
                    getattr(exc, "code", type(exc).__name__),
                )
                continue
        if last_exc is not None:
            raise last_exc
        raise DataSourceUnavailable()

    async def search_accounts(
        self, keyword: str, page: int = 1, page_size: int = 20
    ) -> SearchPage:
        return await self._first_ok("search_accounts", keyword, page, page_size)

    async def search_content(
        self, query: str, page_size: int = 20
    ) -> list[ProviderArticle]:
        return await self._first_ok(
            "search_content",
            query,
            page_size,
            capable=lambda p: getattr(p, "supports_content_search", False),
        )

    async def get_article_metrics(self, article_url: str) -> ProviderMetrics | None:
        # Metrics are keyed by a public URL, so they're portable across sources.
        return await self._first_ok(
            "get_article_metrics",
            article_url,
            capable=lambda p: getattr(p, "supports_metrics", True),
        )

    async def get_account(self, provider_account_id: str) -> ProviderAccount | None:
        # Ids are vendor-specific: only the primary source can resolve them.
        return await self._providers[0].get_account(provider_account_id)

    async def get_articles(
        self,
        provider_account_id: str,
        cursor: str | None = None,
        page_size: int = 20,
        *,
        account_name: str | None = None,
    ) -> ArticlePage:
        return await self._providers[0].get_articles(
            provider_account_id, cursor, page_size, account_name=account_name
        )

    async def get_billing(self) -> dict[str, Any] | None:
        for provider in self._providers:
            fn = getattr(provider, "get_billing", None)
            if fn is None:
                continue
            try:
                result = await fn()
            except Exception:  # pragma: no cover - best-effort
                continue
            if result is not None:
                return result
        return None

    async def aclose(self) -> None:
        for provider in self._providers:
            fn = getattr(provider, "aclose", None)
            if fn is None:
                continue
            try:
                await fn()
            except Exception:  # pragma: no cover - shutdown best-effort
                pass
