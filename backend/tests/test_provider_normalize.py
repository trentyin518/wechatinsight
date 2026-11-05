"""Qovia adapter mapping against the real ``/v1/raw/wechat/*`` endpoints."""

from __future__ import annotations

import httpx
import pytest

from app.core.errors import (
    DataSourceBillingError,
    DataSourceRateLimited,
    DataSourceUnavailable,
    ProviderError,
)
from app.providers.qovia import QoviaProvider


def _provider(handler, *, max_retries: int = 0) -> QoviaProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return QoviaProvider(
        api_key="secret-key", base_url="https://api.test", client=client, max_retries=max_retries
    )


def _account_item(**over):
    item = {
        "id": "soc_wec_x",
        "mp_id": "gh_example",
        "name": "示例公众号",
        "wechat_id": "example_account",
        "avatar": "https://example.com/a.jpg",
        "description": "简介",
        "verified": True,
        "verified_by": "示例机构",
        "type": "subscription",
    }
    item.update(over)
    return item


async def test_account_search_maps_fields():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={"data": {"items": [_account_item()], "cursor": None, "has_more": False}},
        )

    provider = _provider(handler)
    page = await provider.search_accounts("科技")
    assert captured["params"]["keyword"] == "科技"
    assert captured["params"]["kind"] == "all"
    assert len(page.items) == 1
    acc = page.items[0]
    assert acc.provider == "qovia"
    assert acc.provider_account_id == "gh_example"
    assert acc.name == "示例公众号"
    assert acc.wechat_id == "example_account"
    assert acc.verification_subject == "示例机构"
    assert acc.account_type == "subscription"


async def test_articles_maps_and_paginates():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "data": {
                    "items": [
                        {
                            "id": "soc_wec_1",
                            "title": "标题",
                            "url": "https://mp.weixin.qq.com/s?__biz=X",
                            "published_at": "2026-11-03T10:38:20+08:00",
                            "cover": "https://example.com/c.jpg",
                            "digest": "摘要",
                            "author": "作者",
                            "is_original": True,
                            "is_paid": False,
                        }
                    ],
                    "cursor": "NEXT",
                    "has_more": True,
                }
            },
        )

    provider = _provider(handler)
    page = await provider.get_articles("gh_example")
    assert captured["params"]["mp_id"] == "gh_example"
    assert page.next_cursor == "NEXT"
    article = page.items[0]
    assert article.summary == "摘要"
    assert article.is_original is True
    assert article.is_paid is False
    assert article.published_at is not None


async def test_article_metrics_maps_fields():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "data": {
                    "reads": 12434,
                    "likes": 92,
                    "watching": 37,
                    "comments": 9,
                    "shares": 473,
                    "updated_at": "2026-11-03T23:10:30+08:00",
                }
            },
        )

    provider = _provider(handler)
    metrics = await provider.get_article_metrics("https://mp.weixin.qq.com/s?__biz=X")
    assert captured["params"]["url"].startswith("https://mp.weixin.qq.com/")
    assert metrics is not None
    assert metrics.read_count == 12434
    assert metrics.like_count == 92
    assert metrics.wow_count == 37
    assert metrics.comment_count == 9
    assert metrics.share_count == 473
    assert metrics.raw_updated_at is not None


async def test_missing_metric_fields_are_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"reads": 10}})

    provider = _provider(handler)
    metrics = await provider.get_article_metrics("https://mp.weixin.qq.com/s?__biz=X")
    assert metrics is not None
    assert metrics.read_count == 10
    assert metrics.like_count is None
    assert metrics.wow_count is None


async def test_metrics_not_found_returns_none():
    provider = _provider(lambda request: httpx.Response(404, json={"error": {"code": "not_found"}}))
    assert await provider.get_article_metrics("https://mp.weixin.qq.com/s?__biz=X") is None


async def test_timeout_raises_standardized_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    provider = _provider(handler, max_retries=0)
    with pytest.raises(DataSourceUnavailable):
        await provider.search_accounts("科技")


async def test_rate_limit_maps():
    provider = _provider(lambda request: httpx.Response(429, json={"error": {"code": "rate_limited"}}))
    with pytest.raises(DataSourceRateLimited):
        await provider.search_accounts("科技")


async def test_insufficient_balance_maps():
    provider = _provider(
        lambda request: httpx.Response(402, json={"error": {"code": "insufficient_balance"}})
    )
    with pytest.raises(DataSourceBillingError):
        await provider.search_accounts("科技")


async def test_auth_error_does_not_leak():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"code": "invalid_api_key", "secret": "x"}})

    provider = _provider(handler)
    with pytest.raises(ProviderError) as excinfo:
        await provider.search_accounts("科技")
    assert excinfo.value.code == "DATA_SOURCE_AUTH"
    assert "secret" not in str(excinfo.value)
