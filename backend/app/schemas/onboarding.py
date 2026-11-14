"""Onboarding API schemas and canonical option values."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator

SOURCE_CHANNELS = {
    "search_engine",
    "wechat_article",
    "friend_referral",
    "media_site",
    "other",
}

USER_TYPES = {
    "advertiser",
    "brand",
    "agency",
    "public_opinion",
    "account_owner",
    "agency4a",
    "other",
}


class OnboardingSubmitRequest(BaseModel):
    source_channel: str
    source_other: str | None = None
    user_type: str
    user_type_other: str | None = None
    company_name: str
    contact_name: str
    contact_phone: str
    needs: str | None = None
    proof_id: int

    @field_validator("source_channel")
    @classmethod
    def _check_source(cls, value: str) -> str:
        value = (value or "").strip()
        if value not in SOURCE_CHANNELS:
            raise ValueError("请选择有效的获知途径")
        return value

    @field_validator("user_type")
    @classmethod
    def _check_user_type(cls, value: str) -> str:
        value = (value or "").strip()
        if value not in USER_TYPES:
            raise ValueError("请选择有效的用户类型")
        return value

    @field_validator("company_name", "contact_name", "contact_phone")
    @classmethod
    def _required_text(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("此项为必填")
        return value

    @model_validator(mode="after")
    def _check_other(self) -> "OnboardingSubmitRequest":
        if self.source_channel == "other" and not (self.source_other or "").strip():
            raise ValueError("选择「其他」时请填写具体途径")
        if self.user_type == "other" and not (self.user_type_other or "").strip():
            raise ValueError("选择「其他」时请填写具体类型")
        return self


class ProofUploadResponse(BaseModel):
    proof_id: int
    mime_type: str
    size_bytes: int
    original_name: str | None = None


class SubmissionSummary(BaseModel):
    id: int
    status: str
    reject_reason: str | None = None
    submitted_at: datetime
    reviewed_at: datetime | None = None


class OnboardingStatusResponse(BaseModel):
    status: str
    submission: SubmissionSummary | None = None


class SubmissionOut(BaseModel):
    id: int
    user_id: int
    user_phone: str | None = None
    user_display_name: str | None = None
    status: str
    source_channel: str | None = None
    source_other: str | None = None
    user_type: str | None = None
    user_type_other: str | None = None
    company_name: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    needs: str | None = None
    proof_id: int | None = None
    reject_reason: str | None = None
    submitted_at: datetime
    reviewed_at: datetime | None = None


class SubmissionListResponse(BaseModel):
    items: list[SubmissionOut]
    total: int


class ReviewRejectRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def _required(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("请填写驳回原因")
        return value
