"""Multi-source failover behavior."""

from __future__ import annotations

import asyncio

import pytest

from app.core.errors import DataSourceUnavailable
from app.providers.base import (
    ArticlePage,
    ProviderAccount,
    ProviderArticle,
    ProviderMetrics,
    SearchPage,
)
from app.providers.failover import FailoverProvider


class _Fake:
    def __init__(
        self,
        name: str,
        *,
        fail: bool = False,
        supports_content: bool = True,
        accounts: list[ProviderAccount] | None = None,
        content: list[ProviderArticle] | None = None,
        metrics: ProviderMetrics | None = None,
    ) -> None:
        self.name = name
        self._fail = fail
        self.supports_content_search = supports_content
        self.supports_metrics = True
        self._accounts = accounts or []
        self._content = content or []
        self._metrics = metrics
        self.calls: list[str] = []

    async def search_accounts(self, keyword: str, page: int = 1, page_size: int = 20):
        self.calls.append("search_accounts")
        if self._fail:
            raise DataSourceUnavailable()
        return SearchPage(items=list(self._accounts))

    async def search_content(self, query: str, page_size: int = 20):
        self.calls.append("search_content")
        if self._fail:
            raise DataSourceUnavailable()
        return list(self._content)

    async def get_article_metrics(self, article_url: str):
        self.calls.append("get_article_metrics")
        if self._fail:
            raise DataSourceUnavailable()
        return self._metrics

    async def get_account(self, provider_account_id: str):
        self.calls.append("get_account")
        return None

    async def get_articles(
        self, provider_account_id, cursor=None, page_size=20, *, account_name=None
    ):
        self.calls.append("get_articles")
        return ArticlePage(items=[])

    async def get_billing(self):
        return None

    async def aclose(self):
        return None


def _run(coro):
    return asyncio.run(coro)


def test_search_accounts_falls_over_on_failure():
    primary = _Fake("primary", fail=True)
    secondary = _Fake(
        "secondary",
        accounts=[ProviderAccount(provider="secondary", provider_account_id="1", name="N")],
    )
    fp = FailoverProvider([primary, secondary])

    page = _run(fp.search_accounts("k"))
    assert page.items[0].provider == "secondary"
    assert primary.calls == ["search_accounts"]
    assert secondary.calls == ["search_accounts"]
    assert fp.name == "primary"


def test_search_content_skips_unsupported_then_falls_over():
    primary = _Fake("primary", supports_content=False)
    secondary = _Fake(
        "secondary", content=[ProviderArticle(provider="secondary", title="t", url="u")]
    )
    fp = FailoverProvider([primary, secondary])

    items = _run(fp.search_content("k"))
    assert items[0].provider == "secondary"
    assert primary.calls == []  # unsupported → skipped, never called
    assert secondary.calls == ["search_content"]


def test_all_providers_fail_raises():
    fp = FailoverProvider([_Fake("a", fail=True), _Fake("b", fail=True)])
    with pytest.raises(DataSourceUnavailable):
        _run(fp.search_accounts("k"))


def test_metrics_failover_by_url():
    primary = _Fake("primary", fail=True)
    secondary = _Fake(
        "secondary", metrics=ProviderMetrics(provider="secondary", read_count=10)
    )
    fp = FailoverProvider([primary, secondary])

    metrics = _run(fp.get_article_metrics("https://mp.weixin.qq.com/s/a"))
    assert metrics.read_count == 10
    assert metrics.provider == "secondary"


def test_get_account_uses_primary_only():
    primary = _Fake("primary")
    secondary = _Fake("secondary")
    fp = FailoverProvider([primary, secondary])

    _run(fp.get_account("gh_1"))
    assert primary.calls == ["get_account"]
    assert secondary.calls == []
