"""Live content-search fallback (qovia /v1/search) + its guard rails."""

from __future__ import annotations

import dataclasses

from app.core.config import get_settings
from app.providers.base import ProviderArticle
from app.services import articles as articles_service


class _FakeContentProvider:
    name = "fake"
    supports_content_search = True

    def __init__(self) -> None:
        self.calls = 0

    async def search_content(self, query, page_size=20):  # noqa: ANN001, ANN201
        self.calls += 1
        return [
            ProviderArticle(
                provider="fake",
                title="标题",
                url="https://mp.weixin.qq.com/s?x=1",
                author="作者A",
            )
        ]


def _settings(**overrides):
    base = get_settings()
    data = dict(base.__dict__)
    data.update(overrides)
    return base.__class__(**data)


async def test_external_search_maps_and_caches(session):
    articles_service._EXTERNAL_CACHE.clear()
    settings = _settings(content_search_live_enabled=True, content_search_cache_ttl_seconds=600)
    provider = _FakeContentProvider()

    first = await articles_service.search_external_articles(
        session, "阳江日报", provider=provider, settings=settings
    )
    assert len(first) == 1
    assert first[0].author == "作者A"

    # Identical search within the TTL is served from cache (no extra paid call).
    second = await articles_service.search_external_articles(
        session, "阳江日报", provider=provider, settings=settings
    )
    assert len(second) == 1
    assert provider.calls == 1


async def test_external_search_disabled_returns_empty(session):
    articles_service._EXTERNAL_CACHE.clear()
    settings = _settings(content_search_live_enabled=False)
    provider = _FakeContentProvider()
    assert (
        await articles_service.search_external_articles(
            session, "任意", provider=provider, settings=settings
        )
        == []
    )
    assert provider.calls == 0


async def test_external_search_provider_without_support_is_skipped(session):
    articles_service._EXTERNAL_CACHE.clear()
    settings = _settings(content_search_live_enabled=True)

    class _NoContent:
        name = "nocontent"

    assert (
        await articles_service.search_external_articles(
            session, "任意", provider=_NoContent(), settings=settings
        )
        == []
    )


def test_articles_endpoint_falls_back_to_live_content(client, monkeypatch):
    from app.providers.base import ProviderArticle

    class _Fake:
        name = "fake"
        supports_content_search = True

        async def search_content(self, query, page_size=20):  # noqa: ANN001, ANN201
            return [
                ProviderArticle(
                    provider="fake",
                    title="实时标题",
                    url="https://mp.weixin.qq.com/s?__biz=X",
                    author="作者A",
                    is_original=True,
                )
            ]

    articles_service._EXTERNAL_CACHE.clear()
    monkeypatch.setattr(articles_service, "get_provider", lambda: _Fake())

    resp = client.get("/api/v1/articles", params={"q": "阳江日报"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "live"
    assert body["items"], "expected live results, not an empty page"
    item = body["items"][0]
    assert item["external"] is True
    assert item["id"] < 0  # negative id marks external / not stored
    assert item["article_url"].startswith("https://mp.weixin.qq.com/")


async def test_account_search_derives_accounts_from_content(session):
    from app.providers.base import SearchPage
    from app.services import accounts as accounts_service

    class _Fake:
        name = "fake"
        supports_content_search = True

        async def search_accounts(self, keyword, page=1, page_size=20):  # noqa: ANN001, ANN201
            return SearchPage(items=[], next_cursor=None)  # name search is empty

        async def search_content(self, query, page_size=20):  # noqa: ANN001, ANN201
            return [
                ProviderArticle(provider="fake", title="a", url="https://x/1", author="学习与文摘"),
                ProviderArticle(provider="fake", title="b", url="https://x/2", author="学习与文摘"),
                ProviderArticle(
                    provider="fake", title="c", url="https://x/3", author="带着语文书去旅行"
                ),
            ]

    articles_service._EXTERNAL_CACHE.clear()
    settings = _settings(content_search_live_enabled=True, allow_cold_start_search=True)

    result = await accounts_service.search_accounts(
        session, "阳江日报", 1, 20, provider=_Fake(), settings=settings, mode="name"
    )
    assert result.source == "content"
    assert result.total == 2  # deduped by author
    assert {a.name for a in result.items} == {"带着语文书去旅行", "学习与文摘"}


async def test_account_search_breaker_skips_paid_calls_after_empty_streak(session):
    from app.providers.base import SearchPage
    from app.services import accounts as accounts_service

    class _Fake:
        name = "fake"
        supports_content_search = True

        def __init__(self) -> None:
            self.account_calls = 0

        async def search_accounts(self, keyword, page=1, page_size=20):  # noqa: ANN001, ANN201
            self.account_calls += 1
            return SearchPage(items=[], next_cursor=None)

        async def search_content(self, query, page_size=20):  # noqa: ANN001, ANN201
            return [ProviderArticle(provider="fake", title="t", url="https://x/1", author="作者X")]

    accounts_service.reset_account_search_breaker()
    articles_service._EXTERNAL_CACHE.clear()
    settings = _settings(
        content_search_live_enabled=True,
        allow_cold_start_search=True,
        account_search_breaker_threshold=2,
        account_search_breaker_cooldown_seconds=600,
    )
    provider = _Fake()
    for _ in range(4):
        res = await accounts_service.search_accounts(
            session, "阳江日报", 1, 20, provider=provider, settings=settings, mode="name"
        )
        assert res.source == "content"  # never empty: content derivation answers

    # threshold=2: only the first two calls pay for account_search; the breaker
    # then short-circuits the (empty, billed) call for the cooldown window.
    assert provider.account_calls == 2
