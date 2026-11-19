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
