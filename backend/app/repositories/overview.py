"""Read-only aggregate queries backing the homepage overview."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ArticleMetric, WechatAccount, WechatArticle


def counts(session: Session) -> tuple[int, int, int, int, datetime | None]:
    accounts = session.scalar(select(func.count(WechatAccount.id))) or 0
    articles = session.scalar(select(func.count(WechatArticle.id))) or 0
    metrics = session.scalar(select(func.count(ArticleMetric.id))) or 0
    providers = (
        session.scalar(select(func.count(func.distinct(WechatAccount.primary_provider)))) or 0
    )
    last_updated = session.scalar(select(func.max(WechatAccount.last_synced_at)))
    return accounts, articles, metrics, providers, last_updated


def recent_accounts(session: Session, limit: int = 6) -> list[WechatAccount]:
    ordering = func.coalesce(WechatAccount.last_synced_at, WechatAccount.updated_at).desc()
    stmt = (
        select(WechatAccount)
        .order_by(ordering, WechatAccount.id.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt))
