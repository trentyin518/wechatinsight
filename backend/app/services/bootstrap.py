"""Startup bootstrap: idempotently ensure a configured admin account exists."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import OnboardingStatus, User
from app.security import passwords

logger = logging.getLogger("wechat_insight")


def ensure_admin(session: Session, settings: Settings) -> None:
    phone = (settings.admin_phone or "").strip()
    password = settings.admin_password or ""
    if not phone or not password:
        return

    user = session.scalar(select(User).where(User.phone == phone))
    if user is None:
        session.add(
            User(
                phone=phone,
                password_hash=passwords.hash_password(password),
                display_name="管理员",
                is_admin=True,
                onboarding_status=OnboardingStatus.APPROVED,
            )
        )
        session.commit()
        logger.info("Bootstrapped admin account for %s", phone)
        return

    changed = False
    if not user.is_admin:
        user.is_admin = True
        changed = True
    if user.onboarding_status != OnboardingStatus.APPROVED:
        user.onboarding_status = OnboardingStatus.APPROVED
        changed = True
    if not user.password_hash:
        user.password_hash = passwords.hash_password(password)
        changed = True
    if changed:
        session.commit()
