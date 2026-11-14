"""Onboarding: submit info + proof, status, and admin review."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_admin
from app.core.config import get_settings
from app.core.errors import Conflict, NotFoundError, ValidationError
from app.db.models import OnboardingProof, OnboardingStatus, OnboardingSubmission, User
from app.schemas.onboarding import (
    OnboardingStatusResponse,
    OnboardingSubmitRequest,
    ProofUploadResponse,
    ReviewRejectRequest,
    SubmissionListResponse,
    SubmissionOut,
    SubmissionSummary,
)
from app.services.notifications import get_notifier

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}
_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


def _upload_root() -> Path:
    root = Path(get_settings().upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _submission_out(sub: OnboardingSubmission, user: User | None) -> SubmissionOut:
    return SubmissionOut(
        id=sub.id,
        user_id=sub.user_id,
        user_phone=user.phone if user else None,
        user_display_name=user.display_name if user else None,
        status=sub.status,
        source_channel=sub.source_channel,
        source_other=sub.source_other,
        user_type=sub.user_type,
        user_type_other=sub.user_type_other,
        company_name=sub.company_name,
        contact_name=sub.contact_name,
        contact_phone=sub.contact_phone,
        needs=sub.needs,
        proof_id=sub.proof_id,
        reject_reason=sub.reject_reason,
        submitted_at=sub.submitted_at,
        reviewed_at=sub.reviewed_at,
    )


@router.post("/proof", response_model=ProofUploadResponse)
async def upload_proof(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProofUploadResponse:
    settings = get_settings()
    max_bytes = settings.proof_max_mb * 1024 * 1024

    ext = Path(file.filename or "").suffix.lower()
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_TYPES and ext not in _ALLOWED_EXT:
        raise ValidationError("仅支持 JPG/PNG/WEBP/PDF 格式的证明文件。")
    if ext not in _ALLOWED_EXT:
        ext = _ALLOWED_TYPES.get(content_type, ".bin")

    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise ValidationError(f"文件不能超过 {settings.proof_max_mb}MB。")
    if not content:
        raise ValidationError("上传的文件为空。")

    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest = _upload_root() / stored_name
    dest.write_bytes(content)

    mime = content_type if content_type in _ALLOWED_TYPES else "application/octet-stream"
    proof = OnboardingProof(
        user_id=user.id,
        stored_name=stored_name,
        original_name=file.filename,
        mime_type=mime,
        size_bytes=len(content),
    )
    db.add(proof)
    db.commit()
    db.refresh(proof)
    return ProofUploadResponse(
        proof_id=proof.id,
        mime_type=proof.mime_type,
        size_bytes=proof.size_bytes,
        original_name=proof.original_name,
    )


@router.post("/submit", response_model=OnboardingStatusResponse)
def submit(
    payload: OnboardingSubmitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OnboardingStatusResponse:
    if user.onboarding_status == OnboardingStatus.APPROVED:
        raise Conflict("资料已通过审核，无需重复提交。", code="ALREADY_APPROVED")
    if user.onboarding_status == OnboardingStatus.PENDING:
        raise Conflict("资料正在审核中，请耐心等待。", code="ALREADY_PENDING")

    proof = db.get(OnboardingProof, payload.proof_id)
    if proof is None or proof.user_id != user.id:
        raise NotFoundError("证明材料不存在或已失效，请重新上传。")

    submission = OnboardingSubmission(
        user_id=user.id,
        status=OnboardingStatus.PENDING,
        source_channel=payload.source_channel,
        source_other=(payload.source_other or None),
        user_type=payload.user_type,
        user_type_other=(payload.user_type_other or None),
        company_name=payload.company_name,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        needs=(payload.needs or None),
        proof_id=proof.id,
    )
    db.add(submission)
    user.onboarding_status = OnboardingStatus.PENDING
    db.commit()
    db.refresh(submission)
    return OnboardingStatusResponse(
        status=user.onboarding_status,
        submission=SubmissionSummary(
            id=submission.id,
            status=submission.status,
            reject_reason=submission.reject_reason,
            submitted_at=submission.submitted_at,
            reviewed_at=submission.reviewed_at,
        ),
    )


@router.get("/status", response_model=OnboardingStatusResponse)
def status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OnboardingStatusResponse:
    latest = db.scalar(
        select(OnboardingSubmission)
        .where(OnboardingSubmission.user_id == user.id)
        .order_by(OnboardingSubmission.submitted_at.desc(), OnboardingSubmission.id.desc())
    )
    summary = None
    if latest is not None:
        summary = SubmissionSummary(
            id=latest.id,
            status=latest.status,
            reject_reason=latest.reject_reason,
            submitted_at=latest.submitted_at,
            reviewed_at=latest.reviewed_at,
        )
    return OnboardingStatusResponse(status=user.onboarding_status, submission=summary)


@router.get("/submissions", response_model=SubmissionListResponse)
def list_submissions(
    status_filter: str | None = Query(None, alias="status"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SubmissionListResponse:
    stmt = select(OnboardingSubmission)
    if status_filter:
        stmt = stmt.where(OnboardingSubmission.status == status_filter)
    stmt = stmt.order_by(
        OnboardingSubmission.submitted_at.desc(), OnboardingSubmission.id.desc()
    )
    submissions = list(db.scalars(stmt))
    user_ids = {s.user_id for s in submissions}
    users = {
        u.id: u
        for u in db.scalars(select(User).where(User.id.in_(user_ids)))
    } if user_ids else {}
    return SubmissionListResponse(
        items=[_submission_out(s, users.get(s.user_id)) for s in submissions],
        total=len(submissions),
    )


def _get_submission(db: Session, submission_id: int) -> OnboardingSubmission:
    sub = db.get(OnboardingSubmission, submission_id)
    if sub is None:
        raise NotFoundError("登记记录不存在。")
    return sub


@router.post("/submissions/{submission_id}/approve", response_model=SubmissionOut)
def approve(
    submission_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SubmissionOut:
    sub = _get_submission(db, submission_id)
    sub.status = OnboardingStatus.APPROVED
    sub.reviewer_id = admin.id
    sub.reviewed_at = datetime.now(timezone.utc)
    sub.reject_reason = None
    target = db.get(User, sub.user_id)
    if target is not None:
        target.onboarding_status = OnboardingStatus.APPROVED
        get_notifier().onboarding_status_changed(target, OnboardingStatus.APPROVED)
    db.commit()
    db.refresh(sub)
    return _submission_out(sub, target)


@router.post("/submissions/{submission_id}/reject", response_model=SubmissionOut)
def reject(
    submission_id: int,
    payload: ReviewRejectRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SubmissionOut:
    sub = _get_submission(db, submission_id)
    sub.status = OnboardingStatus.REJECTED
    sub.reject_reason = payload.reason
    sub.reviewer_id = admin.id
    sub.reviewed_at = datetime.now(timezone.utc)
    target = db.get(User, sub.user_id)
    if target is not None:
        target.onboarding_status = OnboardingStatus.REJECTED
    if target is not None:
        get_notifier().onboarding_status_changed(
            target, OnboardingStatus.REJECTED, reason=payload.reason
        )
    db.commit()
    db.refresh(sub)
    return _submission_out(sub, target)


@router.get("/submissions/{submission_id}/proof")
def download_proof(
    submission_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FileResponse:
    sub = _get_submission(db, submission_id)
    if sub.proof_id is None:
        raise NotFoundError("该登记没有上传证明文件。")
    proof = db.get(OnboardingProof, sub.proof_id)
    if proof is None:
        raise NotFoundError("证明材料不存在。")

    root = _upload_root().resolve()
    path = (root / proof.stored_name).resolve()
    if root not in path.parents or not path.is_file():
        raise NotFoundError("证明材料不存在。")
    return FileResponse(
        path,
        media_type=proof.mime_type,
        filename=proof.original_name or proof.stored_name,
    )
