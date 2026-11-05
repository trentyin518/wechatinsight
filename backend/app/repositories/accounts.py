"""Account persistence: search, detail and provider-mapping upsert."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import ProviderAccountMapping, WechatAccount
from app.providers.base import ProviderAccount


def get_by_id(session: Session, account_id: int) -> WechatAccount | None:
    return session.get(WechatAccount, account_id)


def search_local(
    session: Session, keyword: str, page: int, page_size: int
) -> tuple[list[WechatAccount], int]:
    stmt = select(WechatAccount)
    count_stmt = select(func.count(WechatAccount.id))
    kw = (keyword or "").strip()
    if kw:
        pattern = f"%{kw}%"
        condition = or_(
            WechatAccount.name.ilike(pattern),
            WechatAccount.wechat_id.ilike(pattern),
            WechatAccount.description.ilike(pattern),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    total = session.scalar(count_stmt) or 0
    stmt = stmt.order_by(WechatAccount.id.desc()).offset((page - 1) * page_size).limit(page_size)
    return list(session.scalars(stmt)), total


def find_by_provider_id(
    session: Session, provider: str, provider_account_id: str
) -> WechatAccount | None:
    mapping = session.scalar(
        select(ProviderAccountMapping).where(
            ProviderAccountMapping.provider == provider,
            ProviderAccountMapping.provider_account_id == provider_account_id,
        )
    )
    return mapping.account if mapping else None


def upsert_from_provider(
    session: Session, data: ProviderAccount, *, priority: str | None = None
) -> WechatAccount:
    """Idempotently create/refresh an account keyed by (provider, provider_id)."""
    account = find_by_provider_id(session, data.provider, data.provider_account_id)
    if account is None:
        account = WechatAccount(
            name=data.name,
            wechat_id=data.wechat_id,
            avatar_url=data.avatar_url,
            description=data.description,
            verification_subject=data.verification_subject,
            account_type=data.account_type,
            primary_provider=data.provider,
        )
        if priority is not None:
            account.priority = priority
        session.add(account)
        session.flush()
        session.add(
            ProviderAccountMapping(
                account_id=account.id,
                provider=data.provider,
                provider_account_id=data.provider_account_id,
            )
        )
    else:
        # Only refresh fields we actually received; never blank out known data.
        for attr in ("name", "wechat_id", "avatar_url", "description", "verification_subject", "account_type"):
            value = getattr(data, attr)
            if value is not None:
                setattr(account, attr, value)
    session.flush()
    return account


def get_provider_account_id(session: Session, account: WechatAccount) -> str | None:
    mapping = session.scalar(
        select(ProviderAccountMapping).where(
            ProviderAccountMapping.account_id == account.id,
            ProviderAccountMapping.provider == account.primary_provider,
        )
    )
    return mapping.provider_account_id if mapping else None


def touch_synced(session: Session, account: WechatAccount, when: datetime | None = None) -> None:
    account.last_synced_at = when or datetime.now(timezone.utc)
    session.flush()
