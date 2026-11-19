"""Admin sync-job health endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.models import JobStatus, JobType, OnboardingStatus, SyncJob, User
from app.main import app
from app.repositories import jobs as jobs_repo
from app.security import passwords
from app.core.config import get_settings

ADMIN_PHONE = "13700137002"
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


def test_admin_sync_health_shape_and_counts(session):
    _add_admin(session)

    pending = jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_ARTICLES,
        target_type="account",
        target_id=1,
        provider="qovia",
    )
    failed = jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_METRICS,
        target_type="article",
        target_id=1,
        provider="qovia",
    )
    failed.status = JobStatus.FAILED
    failed.error_code = "DATA_SOURCE_BILLING"
    session.commit()
    assert pending.id and failed.id

    with TestClient(app) as admin_client:
        login = admin_client.post(
            "/api/v1/auth/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD}
        )
        assert login.status_code == 200

        resp = admin_client.get("/api/v1/admin/sync")
        assert resp.status_code == 200, resp.text
        body = resp.json()

        for key in (
            "status_counts",
            "total_jobs",
            "pending_count",
            "pending_oldest_at",
            "pending_oldest_age_seconds",
            "failed_reasons",
            "recent_failed",
            "by_type",
            "success_24h",
            "failed_24h",
            "worker_hint",
        ):
            assert key in body

        assert body["pending_count"] >= 1
        assert body["total_jobs"] >= 2
        assert any(r["error_code"] == "DATA_SOURCE_BILLING" for r in body["failed_reasons"])
        assert any(j["error_code"] == "DATA_SOURCE_BILLING" for j in body["recent_failed"])
        # Per-type breakdown attributes the backlog to a job type.
        assert isinstance(body["by_type"], list)
        assert any(t["job_type"] == "SYNC_ARTICLES" for t in body["by_type"])


def test_admin_sync_requires_admin(client):
    resp = client.get("/api/v1/admin/sync")
    assert resp.status_code in (401, 403)


def test_admin_sync_drain_triggers(session):
    _add_admin(session)
    job = jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_ARTICLES,
        target_type="account",
        target_id=1,
        provider="mock",
    )
    session.commit()
    assert job.id

    with TestClient(app) as admin_client:
        login = admin_client.post(
            "/api/v1/auth/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD}
        )
        assert login.status_code == 200

        resp = admin_client.post("/api/v1/admin/sync/drain?max_jobs=5")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["scheduled"] is True
        assert body["pending"] >= 1
        assert 1 <= body["max_jobs"] <= 5
        assert body["message"]


def test_admin_sync_drain_empty(session):
    _add_admin(session)
    with TestClient(app) as admin_client:
        login = admin_client.post(
            "/api/v1/auth/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD}
        )
        assert login.status_code == 200

        resp = admin_client.post("/api/v1/admin/sync/drain")
        assert resp.status_code == 200, resp.text
        assert resp.json()["scheduled"] is False


def test_admin_sync_drain_requires_admin(client):
    resp = client.post("/api/v1/admin/sync/drain")
    assert resp.status_code in (401, 403)


def _add_admin2(session):
    session.add(
        User(
            phone="13800138002",
            password_hash=passwords.hash_password("admin1234"),
            display_name="运营B",
            is_admin=True,
            onboarding_status=OnboardingStatus.APPROVED,
        )
    )
    session.commit()


def test_admin_sync_drain_throttles_on_large_metrics_backlog(session):
    _add_admin2(session)
    threshold = get_settings().metrics_backlog_threshold
    for i in range(threshold + 5):
        jobs_repo.create_job(
            session,
            job_type=JobType.SYNC_METRICS,
            target_type="article",
            target_id=i,
            provider="mock",
        )
    session.commit()

    with TestClient(app) as admin_client:
        login = admin_client.post(
            "/api/v1/auth/login",
            json={"phone": "13800138002", "password": "admin1234"},
        )
        assert login.status_code == 200

        resp = admin_client.post("/api/v1/admin/sync/drain")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["scheduled"] is True
        assert body["throttled"] is True
        assert body["metrics_pending"] >= threshold + 5
        assert body["max_jobs"] == get_settings().metrics_backlog_throttled_max_jobs
        assert "节流" in body["message"]
