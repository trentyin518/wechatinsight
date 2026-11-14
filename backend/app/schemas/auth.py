"""Auth API schemas."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.schemas.common import ORMModel

_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


def _validate_phone(value: str) -> str:
    value = (value or "").strip()
    if not _PHONE_RE.fullmatch(value):
        raise ValueError("请输入有效的 11 位手机号")
    return value


def _validate_password(value: str) -> str:
    if len(value) < 8 or len(value) > 64:
        raise ValueError("密码长度需为 8-64 位")
    return value


class RegisterRequest(BaseModel):
    phone: str
    password: str
    display_name: str | None = None

    _phone = field_validator("phone")(_validate_phone)
    _password = field_validator("password")(_validate_password)


class LoginRequest(BaseModel):
    phone: str
    password: str

    _phone = field_validator("phone")(_validate_phone)


class UserOut(ORMModel):
    id: int
    phone: str | None = None
    display_name: str | None = None
    is_admin: bool
    onboarding_status: str
    created_at: datetime


class MeResponse(BaseModel):
    user: UserOut


class WechatAuthorizeResponse(BaseModel):
    authorize_url: str
    configured: bool
    mock_enabled: bool


class WechatMockRequest(BaseModel):
    identity: str | None = None
    display_name: str | None = None
