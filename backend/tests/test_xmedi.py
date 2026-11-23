"""Xmedi (极媒) provider: field mapping + error-code translation."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.core.errors import DataSourceBillingError, DataSourceRateLimited, ProviderError
from app.providers.xmedi import XmediProvider


def _run(handler, coro_factory, *, max_retries: int = 0):
    async def _go():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = XmediProvider(
                api_key="test-key",
                base_url="http://xmedi.test/api/v1",
                client=client,
                max_retries=max_retries,
                backoff=0.0,
            )
            return await coro_factory(provider)

    return asyncio.run(_go())


def test_search_accounts_maps_minimal_rows():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-XMEDI-Key"] == "test-key"
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "items": [{"account_id": "gh_1", "name": "人民日报"}],
                    "has_more": True,
                    "next_cursor": "c2",
                },
            },
        )

    page = _run(handler, lambda p: p.search_accounts("人民日报"))
    assert page.items[0].provider_account_id == "gh_1"
    assert page.items[0].name == "人民日报"
    assert page.items[0].provider == "xmedi"
    assert page.next_cursor == "c2"


def test_search_content_maps_title_and_url():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "items": [
                        {"title": "标题", "url": "https://mp.weixin.qq.com/s/x"}
                    ],
                    "has_more": False,
                },
            },
        )

    items = _run(handler, lambda p: p.search_content("kw", page_size=10))
    assert len(items) == 1
    assert items[0].title == "标题"
    assert items[0].url.startswith("https://mp.weixin.qq.com/")
    assert items[0].provider == "xmedi"


def test_get_articles_maps_fields_and_cursor():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "items": [
                        {
                            "app_msg_id": "m1",
                            "title": "文章A",
                            "url": "https://mp.weixin.qq.com/s/a",
                            "cover": "https://img/cover.jpg",
                            "digest": "摘要",
                            "publish_time": "2026-11-01T08:00:00Z",
                        }
                    ],
                    "has_more": True,
                    "next_cursor": "n2",
                },
            },
        )

    page = _run(handler, lambda p: p.get_articles("gh_1"))
    item = page.items[0]
    assert item.provider_article_id == "m1"
    assert item.title == "文章A"
    assert item.summary == "摘要"
    assert item.cover_url == "https://img/cover.jpg"
    assert item.published_at is not None
    assert page.next_cursor == "n2"


def test_get_article_metrics_maps_counts_without_wow():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "read_num": 100,
                    "like_num": 5,
                    "comment_num": 2,
                    "share_num": 3,
                    "collect_num": 1,
                },
            },
        )

    metrics = _run(handler, lambda p: p.get_article_metrics("https://mp.weixin.qq.com/s/a"))
    assert metrics.read_count == 100
    assert metrics.like_count == 5
    assert metrics.comment_count == 2
    assert metrics.share_count == 3
    assert metrics.wow_count is None
    assert metrics.provider == "xmedi"


def test_metrics_not_found_returns_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404, json={"code": 40400, "error_code": "NOT_FOUND", "message": "nf"}
        )

    metrics = _run(handler, lambda p: p.get_article_metrics("https://mp.weixin.qq.com/s/a"))
    assert metrics is None


def test_unauthorized_maps_to_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"code": 40100, "error_code": "UNAUTHORIZED", "message": "bad key"},
        )

    with pytest.raises(ProviderError) as excinfo:
        _run(handler, lambda p: p.search_accounts("x"))
    assert excinfo.value.code == "DATA_SOURCE_AUTH"


def test_rate_limited_maps():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"code": 42900, "error_code": "RATE_LIMITED", "message": "slow down"},
        )

    with pytest.raises(DataSourceRateLimited):
        _run(handler, lambda p: p.search_accounts("x"))


def test_insufficient_balance_maps():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            402,
            json={
                "code": 40200,
                "error_code": "INSUFFICIENT_BALANCE",
                "message": "no money",
            },
        )

    with pytest.raises(DataSourceBillingError):
        _run(handler, lambda p: p.search_accounts("x"))
