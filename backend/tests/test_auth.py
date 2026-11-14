"""Auth tests: register/login/me/logout, WeChat mock, and enforcement."""

from __future__ import annotations

import dataclasses

import app.api.deps as deps
from app.core.config import get_settings
from app.db.models import OnboardingStatus, User
from app.db.session import SessionLocal
from app.security import passwords

PHONE = "13800138000"
PASSWORD = "secret1234"


def _register(client, phone: str = PHONE, password: str = PASSWORD):
    return client.post("/api/v1/auth/register", json={"phone": phone, "password": password})


def _enable_auth(monkeypatch) -> None:
    real = get_settings()
    monkeypatch.setattr(deps, "get_settings", lambda: dataclasses.replace(real, auth_enforced=True))


def test_register_sets_session_and_me(client):
    resp = _register(client)
    assert resp.status_code == 200, resp.text
    body = resp.json()["user"]
    assert body["phone"] == PHONE
    assert body["onboarding_status"] == OnboardingStatus.NONE

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["phone"] == PHONE


def test_register_duplicate_phone(client):
    assert _register(client).status_code == 200
    dup = _register(client)
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "PHONE_TAKEN"


def test_register_rejects_bad_phone(client):
    bad = client.post("/api/v1/auth/register", json={"phone": "123", "password": PASSWORD})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_wrong_password(client):
    _register(client)
    client.post("/api/v1/auth/logout")
    resp = client.post("/api/v1/auth/login", json={"phone": PHONE, "password": "wrongpass1"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_success(client):
    _register(client)
    client.post("/api/v1/auth/logout")
    resp = client.post("/api/v1/auth/login", json={"phone": PHONE, "password": PASSWORD})
    assert resp.status_code == 200
    assert resp.json()["user"]["phone"] == PHONE


def test_me_requires_auth(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_logout_revokes_session(client):
    _register(client)
    assert client.get("/api/v1/auth/me").status_code == 200
    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_wechat_authorize_reports_mock(client):
    resp = client.get("/api/v1/auth/wechat/authorize")
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is False
    assert body["mock_enabled"] is True
    assert body["authorize_url"] == ""


def test_wechat_mock_login(client):
    resp = client.post("/api/v1/auth/wechat/mock", json={"identity": "tester"})
    assert resp.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 200


def test_enforcement_requires_login(client, monkeypatch):
    _enable_auth(monkeypatch)
    resp = client.get("/api/v1/accounts", params={"q": "x"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_enforcement_blocks_unapproved(client, monkeypatch):
    _register(client)  # onboarding_status == none
    _enable_auth(monkeypatch)
    resp = client.get("/api/v1/accounts", params={"q": "x"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ONBOARDING_REQUIRED"


def test_enforcement_allows_approved(client, monkeypatch):
    db = SessionLocal()
    try:
        admin = User(
            phone="13900139000",
            password_hash=passwords.hash_password(PASSWORD),
            is_admin=False,
            onboarding_status=OnboardingStatus.APPROVED,
        )
        db.add(admin)
        db.commit()
    finally:
        db.close()

    login = client.post("/api/v1/auth/login", json={"phone": "13900139000", "password": PASSWORD})
    assert login.status_code == 200

    _enable_auth(monkeypatch)
    resp = client.get("/api/v1/accounts", params={"q": "示例"})
    assert resp.status_code == 200
