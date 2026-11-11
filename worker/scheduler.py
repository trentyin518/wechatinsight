"""Scheduling: enqueue due work by tier and drive the engine on an interval.

MVP uses a single-process APScheduler + DB job table (no Redis/Celery yet).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import (
    JobStatus,
    JobType,
    Priority,
    SyncJob,
    WechatAccount,
    WechatArticle,
)
from app.db.session import SessionLocal
from app.providers.registry import get_provider
from app.repositories import jobs as jobs_repo
from worker import engine

logger = logging.getLogger("wechat_insight.scheduler")

# Coarse tier intervals (hours). Real frequencies are tuned after Phase 0.
TIER_INTERVAL_HOURS = {Priority.A: 6, Priority.B: 12, Priority.C: 24}

# After a job exhausts its retries, stop re-enqueueing the same target for a
# while. Without this a permanently failing endpoint (e.g. a metrics route the
# provider does not expose) spawns a fresh job every cycle forever.
FAILED_COOLDOWN = timedelta(hours=6)


def _active_job(session: Session, job_type: str, target_id: int) -> bool:
    stmt = select(SyncJob.id).where(
        SyncJob.job_type == job_type,
        SyncJob.target_id == target_id,
        SyncJob.status.in_([JobStatus.PENDING, JobStatus.RUNNING, JobStatus.RETRY]),
    )
    if session.scalar(stmt) is not None:
        return True
    recent_failure = (
        select(SyncJob.id)
        .where(
            SyncJob.job_type == job_type,
            SyncJob.target_id == target_id,
            SyncJob.status == JobStatus.FAILED,
            SyncJob.finished_at >= datetime.now(timezone.utc) - FAILED_COOLDOWN,
        )
        .limit(1)
    )
    return session.scalar(recent_failure) is not None


def _is_due(account: WechatAccount, now: datetime) -> bool:
    if account.last_synced_at is None:
        return True
    last = account.last_synced_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    interval = timedelta(hours=TIER_INTERVAL_HOURS.get(account.priority, 12))
    return now - last >= interval


def enqueue_account_sync(session: Session, account: WechatAccount) -> SyncJob | None:
    if _active_job(session, JobType.SYNC_ACCOUNT, account.id):
        return None
    return jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_ACCOUNT,
        target_type="account",
        target_id=account.id,
        provider=account.primary_provider,
        priority=account.priority,
    )


def enqueue_articles_sync(session: Session, account: WechatAccount) -> SyncJob | None:
    if _active_job(session, JobType.SYNC_ARTICLES, account.id):
        return None
    return jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_ARTICLES,
        target_type="account",
        target_id=account.id,
        provider=account.primary_provider,
        priority=account.priority,
    )


def enqueue_metrics_sync(
    session: Session, article: WechatArticle, priority: str = Priority.B
) -> SyncJob | None:
    if _active_job(session, JobType.SYNC_METRICS, article.id):
        return None
    return jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_METRICS,
        target_type="article",
        target_id=article.id,
        provider=article.provider,
        priority=priority,
    )


def enqueue_due_work(
    session: Session, settings: Settings | None = None, *, article_limit: int = 50
) -> int:
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    enqueued = 0

    for account in session.scalars(select(WechatAccount)).all():
        if not _is_due(account, now):
            continue
        if enqueue_account_sync(session, account):
            enqueued += 1
        if enqueue_articles_sync(session, account):
            enqueued += 1

    recent_articles = session.scalars(
        select(WechatArticle).order_by(WechatArticle.id.desc()).limit(article_limit)
    ).all()
    account_priority = {
        a.id: a.priority for a in session.scalars(select(WechatAccount)).all()
    }
    for article in recent_articles:
        if not getattr(get_provider(article.provider), "supports_metrics", True):
            continue  # provider has no metrics endpoint; don't spend/guesstimate
        priority = account_priority.get(article.account_id, Priority.B)
        if enqueue_metrics_sync(session, article, priority=priority):
            enqueued += 1
    return enqueued


async def run_cycle(max_jobs: int = 50) -> dict[str, int]:
    session = SessionLocal()
    try:
        settings = get_settings()
        enqueued = enqueue_due_work(session, settings)
        session.commit()
        processed = await engine.run_pending(session, max_jobs=max_jobs, settings=settings)
        return {"enqueued": enqueued, "processed": processed}
    finally:
        session.close()


def run_cycle_sync(max_jobs: int = 50) -> dict[str, int]:
    return asyncio.run(run_cycle(max_jobs=max_jobs))


def build_scheduler(interval_seconds: int = 300):
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_cycle_sync,
        "interval",
        seconds=interval_seconds,
        id="sync_cycle",
        max_instances=1,
        coalesce=True,
    )
    return scheduler
