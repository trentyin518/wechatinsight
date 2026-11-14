"""Authentication endpoints: phone/password and WeChat QR (real + mock)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import extract_token, get_current_user, get_db
from app.core.config import Settings, get_settings
from app.core.errors import Conflict, Forbidden, Unauthenticated
from app.db.models import OnboardingStatus, User
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    RegisterRequest,
    UserOut,
    WechatAuthorizeResponse,
    WechatMockRequest,
)
from app.security import passwords
from app.security import sessions as session_service
from app.security import state as state_service
from app.services import wechat as wechat_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _cookie_kwargs(settings: Settings) -> dict:
    return {
        "key": settings.session_cookie_name,
        "httponly": True,
        "samesite": "lax",
        "secure": settings.is_production,
        "max_age": settings.session_ttl_hours * 3600,
        "path": "/",
    }


def _issue_session(response: Response, db: Session, request: Request, user: User) -> None:
    settings = get_settings()
    token, _ = session_service.create_session(
        db,
        user.id,
        settings.session_ttl_hours,
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    response.set_cookie(value=token, **_cookie_kwargs(settings))


def _me(user: User) -> MeResponse:
    return MeResponse(user=UserOut.model_validate(user))


def _upsert_wechat_user(
    db: Session,
    *,
    unionid: str | None,
    openid: str | None,
    nickname: str | None,
) -> User:
    user: User | None = None
    if unionid:
        user = db.scalar(select(User).where(User.wechat_unionid == unionid))
    if user is None and openid:
        user = db.scalar(select(User).where(User.wechat_openid == openid))
    if user is None:
        user = User(
            wechat_unionid=unionid,
            wechat_openid=openid,
            display_name=nickname,
            onboarding_status=OnboardingStatus.NONE,
        )
        db.add(user)
        db.flush()
    else:
        if unionid and not user.wechat_unionid:
            user.wechat_unionid = unionid
        if openid and not user.wechat_openid:
            user.wechat_openid = openid
        if nickname and not user.display_name:
            user.display_name = nickname
    return user


@router.post("/register", response_model=MeResponse)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> MeResponse:
    existing = db.scalar(select(User).where(User.phone == payload.phone))
    if existing is not None:
        raise Conflict("该手机号已注册，请直接登录。", code="PHONE_TAKEN")
    user = User(
        phone=payload.phone,
        password_hash=passwords.hash_password(payload.password),
        display_name=(payload.display_name or None),
        onboarding_status=OnboardingStatus.NONE,
    )
    db.add(user)
    db.flush()
    _issue_session(response, db, request, user)
    db.commit()
    return _me(user)


@router.post("/login", response_model=MeResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> MeResponse:
    user = db.scalar(select(User).where(User.phone == payload.phone))
    if user is None or not passwords.verify_password(payload.password, user.password_hash):
        raise Unauthenticated("手机号或密码错误。", code="INVALID_CREDENTIALS")
    _issue_session(response, db, request, user)
    db.commit()
    return _me(user)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)) -> MeResponse:
    return _me(user)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    settings = get_settings()
    session_service.revoke_session(db, extract_token(request))
    db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"ok": True}


@router.get("/wechat/authorize", response_model=WechatAuthorizeResponse)
def wechat_authorize() -> WechatAuthorizeResponse:
    settings = get_settings()
    configured = wechat_service.wechat_configured(settings)
    if configured:
        state = state_service.sign_state(settings.session_secret)
        url = wechat_service.build_authorize_url(settings, state)
    else:
        url = ""
    mock_enabled = (not configured) and (not settings.is_production)
    return WechatAuthorizeResponse(
        authorize_url=url, configured=configured, mock_enabled=mock_enabled
    )


@router.get("/wechat/callback")
async def wechat_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> Response:
    settings = get_settings()
    if not state_service.verify_state(settings.session_secret, state, settings.wechat_state_ttl_seconds):
        raise Unauthenticated("登录校验失败，请重新扫码。", code="INVALID_STATE")
    identity = await wechat_service.exchange_code(settings, code)
    user = _upsert_wechat_user(
        db, unionid=identity.unionid, openid=identity.openid, nickname=identity.nickname
    )
    redirect = RedirectResponse(
        url=f"{settings.frontend_base_url.rstrip('/')}/onboarding", status_code=302
    )
    _issue_session(redirect, db, request, user)
    db.commit()
    return redirect


@router.post("/wechat/mock", response_model=MeResponse)
def wechat_mock(
    payload: WechatMockRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> MeResponse:
    settings = get_settings()
    if settings.is_production:
        raise Forbidden("mock 登录仅用于开发环境。", code="MOCK_DISABLED")
    identity = (payload.identity or "").strip() or "demo"
    openid = f"mock:{identity}"
    user = _upsert_wechat_user(
        db, unionid=None, openid=openid, nickname=(payload.display_name or f"体验用户-{identity[:6]}")
    )
    _issue_session(response, db, request, user)
    db.commit()
    return _me(user)
