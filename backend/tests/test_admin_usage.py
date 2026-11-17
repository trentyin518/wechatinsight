"""Admin usage/budget overview endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.models import OnboardingStatus, User
from app.main import app
from app.security import passwords

ADMIN_PHONE = "13700137001"
ADMIN_PASSWORD = "admin1234"


def _add_admin(session):
    session.add(
        User(
            phone=ADMIN_PHONE,
            password_hash=passwords.hash_password(ADMIN_PASSWORD),
            display_name="运营",
            is_admin=True,
            onboarding_status=OnboardingStatus.APPROVED,
        )
    )
    session.commit()


def test_admin_usage_overview_shape(session):
    _add_admin(session)
    with TestClient(app) as admin_client:
        login = admin_client.post(
            "/api/v1/auth/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD}
        )
        assert login.status_code == 200

        resp = admin_client.get("/api/v1/admin/usage")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        for key in (
            "balance_usd",
            "daily_cost_usd",
            "monthly_cost_usd",
            "daily_budget_usd",
            "monthly_budget_usd",
            "today_calls",
            "collection_enabled",
            "search_retry_enabled",
            "over_daily_budget",
            "over_monthly_budget",
            "recent",
        ):
            assert key in body
        assert isinstance(body["recent"], list)


def test_admin_usage_requires_admin(client):
    resp = client.get("/api/v1/admin/usage")
    assert resp.status_code in (401, 403)
