"""FastAPI dependencies, including authentication and access control."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Forbidden, Unauthenticated
from app.db.models import OnboardingStatus, User
from app.db.session import get_session
from app.security import sessions as session_service


def get_db() -> Iterator[Session]:
    yield from get_session()


def extract_token(request: Request) -> str | None:
    """Read the session token from the cookie first, then a Bearer header."""
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        return token
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def get_optional_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    token = extract_token(request)
    if not token:
        return None
    return session_service.resolve_user(db, token)


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    user = get_optional_user(request, db)
    if user is None:
        raise Unauthenticated()
    return user


def require_approved(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    """Gate data endpoints behind an approved session.

    When ``AUTH_ENFORCED`` is false (gray rollout), the endpoints stay public:
    any resolved user is returned and anonymous access is allowed.
    """
    settings = get_settings()
    user = get_optional_user(request, db)
    if not settings.auth_enforced:
        return user
    if user is None:
        raise Unauthenticated()
    status = user.onboarding_status
    if status == OnboardingStatus.APPROVED:
        return user
    if status == OnboardingStatus.PENDING:
        raise Forbidden("资料正在审核中，审核通过后即可使用。", code="ONBOARDING_PENDING")
    if status == OnboardingStatus.REJECTED:
        raise Forbidden("资料未通过审核，请修改后重新提交。", code="ONBOARDING_REJECTED")
    raise Forbidden("请先完成信息登记。", code="ONBOARDING_REQUIRED")


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise Forbidden()
    return user
