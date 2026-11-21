"""On-demand, search-triggered collection scheduling.

MVP keeps background collection OFF (``COLLECTION_ENABLED=false``): no timer
sweeps every account, and nothing is fetched proactively. Instead, when a
user's *search* returns accounts on the visible result page, exactly those
accounts get a single background ``SYNC_ARTICLES`` job — first page of articles
only. That job persists the articles and chains a bounded number of
``SYNC_METRICS`` jobs, so the console can finally show real
发文篇数 / 头条平均* values.

All work here is demand-gated: an account is collected at most once inside the
configured TTL, and an identical search condition is never charged twice
(keyword cache + per-account TTL). Nothing runs on a schedule.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import JobStatus, JobType, SyncJob, WechatAccount, WechatArticle
from app.repositories import accounts as accounts_repo
from app.repositories import articles as articles_repo
from app.repositories import jobs as jobs_repo

logger = logging.getLogger("wechat_insight.collection")

_ACTIVE_STATUSES = (JobStatus.PENDING, JobStatus.RUNNING, JobStatus.RETRY)
# A provider may be permanently sick for a given account; stop re-enqueueing a
# failed job for a while so we don't burn budget retrying the same dead end.
_FAILED_COOLDOWN_HOURS = 6


def _has_recent_job(session: Session, job_type: str, target_id: int) -> bool:
    """True when a job is in-flight or recently failed for this target."""
    active = session.scalar(
        select(SyncJob.id).where(
            SyncJob.job_type == job_type,
            SyncJob.target_id == target_id,
            SyncJob.status.in_(_ACTIVE_STATUSES),
        )
    )
    if active is not None:
        return True
    recent_failure = session.scalar(
        select(SyncJob.id)
        .where(
            SyncJob.job_type == job_type,
            SyncJob.target_id == target_id,
            SyncJob.status == JobStatus.FAILED,
            SyncJob.finished_at >= datetime.now(timezone.utc)
            - timedelta(hours=_FAILED_COOLDOWN_HOURS),
        )
        .limit(1)
    )
    return recent_failure is not None


def _is_stale(account: WechatAccount, now: datetime, ttl_hours: int) -> bool:
    """True when the account is due for an on-demand re-collection."""
    if account.last_synced_at is None:
        return True
    last = account.last_synced_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return now - last >= timedelta(hours=ttl_hours)


def enqueue_accounts_for_sync(
    session: Session,
    accounts: Iterable[WechatAccount],
    *,
    settings: Settings | None = None,
) -> int:
    """Enqueue one SYNC_ARTICLES job per account that deserves collection.

    Returns the number of jobs created. Idempotent: accounts collected inside
    ``on_demand_sync_ttl_hours`` or already in-flight are skipped.
    """
    settings = settings or get_settings()
    if not settings.on_demand_sync_enabled:
        return 0

    now = datetime.now(timezone.utc)
    created = 0
    for account in accounts:
        if not _is_stale(account, now, settings.on_demand_sync_ttl_hours):
            continue
        provider_account_id = accounts_repo.get_provider_account_id(session, account)
        if provider_account_id is None or provider_account_id.startswith("content:"):
            # No mapping to fetch articles with (or a content-derived stub with
            # no real mp_id) — don't spend a paid call on it.
            continue
        if _has_recent_job(session, JobType.SYNC_ARTICLES, account.id):
            continue
        jobs_repo.create_job(
            session,
            job_type=JobType.SYNC_ARTICLES,
            target_type="account",
            target_id=account.id,
            provider=account.primary_provider,
            priority=account.priority,
        )
        created += 1
    return created


def _active_job_exists(session: Session, job_type: str, target_id: int) -> bool:
    """True when a job of this type is currently in-flight for the target."""
    return (
        session.scalar(
            select(SyncJob.id)
            .where(
                SyncJob.job_type == job_type,
                SyncJob.target_id == target_id,
                SyncJob.status.in_(_ACTIVE_STATUSES),
            )
            .limit(1)
        )
        is not None
    )


def force_enqueue_articles(
    session: Session,
    account: WechatAccount,
) -> int | None:
    """Force-enqueue a SYNC_ARTICLES job for one account, bypassing TTL/cooldown.

    Used by the console's manual "重新采集" button: an operator explicitly wants
    a fresh pull even if the account was synced recently or a prior attempt
    failed. We still skip only when an identical job is *currently in-flight* to
    avoid duplicates. Returns the new job id, or ``None`` if already in-flight.
    """
    if _active_job_exists(session, JobType.SYNC_ARTICLES, account.id):
        return None
    job = jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_ARTICLES,
        target_type="account",
        target_id=account.id,
        provider=account.primary_provider,
        priority=account.priority,
    )
    return job.id


def enqueue_metrics_for_account(
    session: Session,
    account: WechatAccount,
    *,
    settings: Settings | None = None,
    limit: int | None = None,
) -> int:
    """Enqueue SYNC_METRICS jobs for an account's latest articles (bounded).

    Articles whose metrics were fetched inside ``metrics_min_interval_hours`` or
    that already have an in-flight metrics job are skipped. Returns the number
    of jobs created.
    """
    settings = settings or get_settings()
    cap = settings.metrics_per_account_limit if limit is None else limit
    if cap <= 0:
        return 0

    from app.providers.registry import get_provider

    try:
        provider = get_provider(account.primary_provider)
    except Exception:  # unknown/disabled provider: nothing to measure
        logger.warning("cannot schedule metrics for %s: unknown provider %r", account.id, account.primary_provider)
        return 0
    if not getattr(provider, "supports_metrics", True):
        return 0

    article_ids = list(
        session.scalars(
            select(WechatArticle.id)
            .where(WechatArticle.account_id == account.id)
            .order_by(WechatArticle.published_at.desc().nullslast(), WechatArticle.id.desc())
            .limit(cap)
        )
    )
    if not article_ids:
        return 0

    # Only the articles that already have a recent snapshot are skipped; the
    # rest (including articles with no metrics at all) get a job.
    latest = articles_repo.latest_metric_map(session, article_ids)
    min_interval = timedelta(hours=settings.metrics_min_interval_hours)
    now = datetime.now(timezone.utc)
    created = 0
    for article_id in article_ids:
        existing = latest.get(article_id)
        if existing is not None:
            observed = existing.observed_at
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            if now - observed < min_interval:
                continue
        if _has_recent_job(session, JobType.SYNC_METRICS, article_id):
            continue
        jobs_repo.create_job(
            session,
            job_type=JobType.SYNC_METRICS,
            target_type="article",
            target_id=article_id,
            provider=account.primary_provider,
            priority=account.priority,
        )
        created += 1
    return created
