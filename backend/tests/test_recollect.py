"""Per-account manual re-collection (force enqueue) + endpoint."""

from __future__ import annotations

from app.db.models import ProviderAccountMapping, WechatAccount
from app.services import collection as collection_service


def _make_account(session, *, account_id: int, provider: str = "mock") -> WechatAccount:
    account = WechatAccount(
        id=account_id,
        name=f"测试号{account_id}",
        wechat_id=f"wx{account_id}",
        primary_provider=provider,
    )
    session.add(account)
    session.flush()
    return account


def test_force_enqueue_articles_skips_only_in_flight(session):
    account = _make_account(session, account_id=1)
    session.commit()

    job_id = collection_service.force_enqueue_articles(session, account)
    session.commit()
    assert job_id is not None

    # A second force while the first is still PENDING must not duplicate.
    assert collection_service.force_enqueue_articles(session, account) is None


def test_recollect_endpoint_requires_mapping(client, session):
    _make_account(session, account_id=2)  # no provider mapping
    session.commit()

    resp = client.post("/api/v1/accounts/2/recollect")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["queued"] is False
    assert body["job_id"] is None
    assert "映射" in body["message"]


def test_recollect_endpoint_queues_job(client, session):
    account = _make_account(session, account_id=3)
    session.add(
        ProviderAccountMapping(
            account_id=account.id, provider="mock", provider_account_id="mock-3"
        )
    )
    session.commit()

    resp = client.post("/api/v1/accounts/3/recollect")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["queued"] is True
    assert body["job_id"] is not None


def test_recollect_endpoint_unknown_account(client):
    resp = client.post("/api/v1/accounts/99999/recollect")
    assert resp.status_code == 404
