"""/api/v1 contract tests (health, accounts, articles, error envelope)."""

from __future__ import annotations

import asyncio

from app.db.models import WechatArticle
from app.db.session import SessionLocal
from app.providers.base import ProviderAccount
from app.providers.mock import MockProvider
from app.repositories import accounts as accounts_repo
from worker import engine, scheduler


def _populate_articles() -> int:
    db = SessionLocal()
    try:
        accounts_repo.upsert_from_provider(
            db,
            ProviderAccount(
                provider="mock",
                provider_account_id="mock-1001",
                name="示例科技观察",
                wechat_id="mock_tech",
            ),
        )
        db.commit()
        for _ in range(2):
            scheduler.enqueue_due_work(db)
            db.commit()
            asyncio.run(engine.run_pending(db, provider=MockProvider()))
        return db.query(WechatArticle.id).order_by(WechatArticle.id).first()[0]
    finally:
        db.close()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_search_cold_start_then_local(client):
    first = client.get("/api/v1/accounts", params={"q": "示例"})
    assert first.status_code == 200
    body = first.json()
    assert body["total"] >= 1
    assert body["items"]
    assert body["items"][0]["provider"] == "mock"

    second = client.get("/api/v1/accounts", params={"q": "示例"})
    assert second.status_code == 200
    assert second.json()["total"] == body["total"]


def test_account_detail_not_found(client):
    resp = client.get("/api/v1/accounts/999999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_validation_error_envelope(client):
    resp = client.get("/api/v1/accounts", params={"page": 0})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "message" in body["error"]


def test_article_detail_and_metrics(client):
    article_id = _populate_articles()

    detail = client.get(f"/api/v1/articles/{article_id}")
    assert detail.status_code == 200
    dbody = detail.json()
    assert dbody["title"]
    assert dbody["metrics"] is not None
    assert dbody["metrics"]["read_count"] is not None

    history = client.get(f"/api/v1/articles/{article_id}/metrics")
    assert history.status_code == 200
    hbody = history.json()
    assert len(hbody["points"]) >= 1
    # Points are chronologically ordered.
    observed = [p["observed_at"] for p in hbody["points"]]
    assert observed == sorted(observed)


def test_article_not_found(client):
    resp = client.get("/api/v1/articles/999999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_openapi_exposes_p0_endpoints(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    for path in (
        "/api/v1/accounts",
        "/api/v1/accounts/{account_id}",
        "/api/v1/accounts/{account_id}/articles",
        "/api/v1/articles/{article_id}",
        "/api/v1/articles/{article_id}/metrics",
    ):
        assert path in paths
