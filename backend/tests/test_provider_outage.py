"""Fault injection for 8.3: a provider outage must not take the site down."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.errors import DataSourceUnavailable
from app.db.models import WechatAccount
from app.services import accounts as accounts_service


class _BrokenProvider:
    """Every upstream call fails, simulating a third-party outage."""

    name = "broken"

    async def search_accounts(self, keyword: str, page: int = 1, page_size: int = 20):
        raise DataSourceUnavailable()

    async def get_account(self, provider_account_id: str):
        raise DataSourceUnavailable()

    async def get_articles(
        self,
        provider_account_id: str,
        cursor: str | None = None,
        page_size: int = 20,
        *,
        account_name: str | None = None,
    ):
        raise DataSourceUnavailable()

    async def get_article_metrics(self, article_url: str):
        raise DataSourceUnavailable()


@pytest.fixture
def provider_outage(monkeypatch) -> None:
    monkeypatch.setattr(accounts_service, "get_provider", lambda *a, **k: _BrokenProvider())


def test_health_stays_up_during_outage(client: TestClient, provider_outage: None) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cold_search_degrades_to_503_envelope(client: TestClient, provider_outage: None) -> None:
    response = client.get("/api/v1/accounts", params={"q": "zzz-not-cached-keyword"})
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "DATA_SOURCE_UNAVAILABLE"
    assert body["error"]["message"] == "当前暂时无法更新数据，请稍后重试。"


def test_cached_search_never_calls_provider(client, session, provider_outage: None) -> None:
    session.add(
        WechatAccount(
            name="本地缓存号", wechat_id="cached_1", primary_provider="mock", priority="B"
        )
    )
    session.commit()

    response = client.get("/api/v1/accounts", params={"q": "本地缓存号"})
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_detail_endpoints_still_serve_cached_data(client, session, provider_outage: None) -> None:
    account = WechatAccount(
        name="缓存详情号", wechat_id="cached_2", primary_provider="mock", priority="B"
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    assert client.get(f"/api/v1/accounts/{account.id}").status_code == 200
    assert client.get(f"/api/v1/accounts/{account.id}/articles").status_code == 200
