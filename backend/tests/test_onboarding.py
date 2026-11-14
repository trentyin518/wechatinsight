"""Onboarding tests: proof upload, submit, status, and admin review."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.models import OnboardingStatus, User
from app.main import app
from app.security import passwords

APPLICANT_PHONE = "13800138000"
PASSWORD = "secret1234"
ADMIN_PHONE = "13700137000"
ADMIN_PASSWORD = "admin1234"


def _register(client, phone: str = APPLICANT_PHONE):
    return client.post("/api/v1/auth/register", json={"phone": phone, "password": PASSWORD})


def _upload(client):
    files = {"file": ("proof.png", b"\x89PNG\r\n\x1a\nfake-bytes", "image/png")}
    return client.post("/api/v1/onboarding/proof", files=files)


def _payload(proof_id: int, **overrides) -> dict:
    base = {
        "source_channel": "search_engine",
        "user_type": "advertiser",
        "company_name": "测试公司",
        "contact_name": "张三",
        "contact_phone": "13800138000",
        "needs": "了解数据",
        "proof_id": proof_id,
    }
    base.update(overrides)
    return base


def _add_admin(session):
    session.add(
        User(
            phone=ADMIN_PHONE,
            password_hash=passwords.hash_password(ADMIN_PASSWORD),
            display_name="审核员",
            is_admin=True,
            onboarding_status=OnboardingStatus.APPROVED,
        )
    )
    session.commit()


def test_proof_upload_and_submit(client):
    _register(client)
    up = _upload(client)
    assert up.status_code == 200, up.text
    proof_id = up.json()["proof_id"]

    submit = client.post("/api/v1/onboarding/submit", json=_payload(proof_id))
    assert submit.status_code == 200, submit.text
    assert submit.json()["status"] == OnboardingStatus.PENDING

    status = client.get("/api/v1/onboarding/status")
    assert status.status_code == 200
    assert status.json()["status"] == OnboardingStatus.PENDING

    me = client.get("/api/v1/auth/me")
    assert me.json()["user"]["onboarding_status"] == OnboardingStatus.PENDING


def test_submit_missing_required_field(client):
    _register(client)
    proof_id = _upload(client).json()["proof_id"]
    resp = client.post("/api/v1/onboarding/submit", json=_payload(proof_id, company_name="  "))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_submit_other_requires_text(client):
    _register(client)
    proof_id = _upload(client).json()["proof_id"]
    resp = client.post(
        "/api/v1/onboarding/submit", json=_payload(proof_id, source_channel="other")
    )
    assert resp.status_code == 422


def test_submit_with_unknown_proof(client):
    _register(client)
    resp = client.post("/api/v1/onboarding/submit", json=_payload(999999))
    assert resp.status_code == 404


def test_duplicate_pending_rejected(client):
    _register(client)
    proof_id = _upload(client).json()["proof_id"]
    first = client.post("/api/v1/onboarding/submit", json=_payload(proof_id))
    assert first.status_code == 200
    second = client.post("/api/v1/onboarding/submit", json=_payload(proof_id))
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "ALREADY_PENDING"


def test_proof_invalid_type(client):
    _register(client)
    files = {"file": ("secret.txt", b"hello", "text/plain")}
    resp = client.post("/api/v1/onboarding/proof", files=files)
    assert resp.status_code == 422


def test_non_admin_cannot_list(client):
    _register(client)
    resp = client.get("/api/v1/onboarding/submissions")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_admin_approve_flow(client, session):
    _register(client)
    proof_id = _upload(client).json()["proof_id"]
    submit = client.post("/api/v1/onboarding/submit", json=_payload(proof_id))
    submission_id = submit.json()["submission"]["id"]

    _add_admin(session)

    with TestClient(app) as admin_client:
        login = admin_client.post(
            "/api/v1/auth/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD}
        )
        assert login.status_code == 200

        listing = admin_client.get("/api/v1/onboarding/submissions", params={"status": "pending"})
        assert listing.status_code == 200
        assert listing.json()["total"] >= 1

        # The proof is retrievable by an admin.
        proof = admin_client.get(f"/api/v1/onboarding/submissions/{submission_id}/proof")
        assert proof.status_code == 200

        approve = admin_client.post(f"/api/v1/onboarding/submissions/{submission_id}/approve")
        assert approve.status_code == 200
        assert approve.json()["status"] == OnboardingStatus.APPROVED

    assert client.get("/api/v1/onboarding/status").json()["status"] == OnboardingStatus.APPROVED


def test_admin_reject_and_resubmit(client, session):
    _register(client)
    proof_id = _upload(client).json()["proof_id"]
    submission_id = client.post("/api/v1/onboarding/submit", json=_payload(proof_id)).json()[
        "submission"
    ]["id"]

    _add_admin(session)

    with TestClient(app) as admin_client:
        admin_client.post(
            "/api/v1/auth/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD}
        )
        reject = admin_client.post(
            f"/api/v1/onboarding/submissions/{submission_id}/reject",
            json={"reason": "证明材料不清晰"},
        )
        assert reject.status_code == 200
        assert reject.json()["status"] == OnboardingStatus.REJECTED

    status = client.get("/api/v1/onboarding/status").json()
    assert status["status"] == OnboardingStatus.REJECTED
    assert status["submission"]["reject_reason"] == "证明材料不清晰"

    # A rejected user may resubmit (returns to pending).
    resubmit = client.post("/api/v1/onboarding/submit", json=_payload(proof_id))
    assert resubmit.status_code == 200
    assert resubmit.json()["status"] == OnboardingStatus.PENDING
