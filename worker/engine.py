"""Job execution engine: dispatch, state machine, usage accounting."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ProviderError
from app.db.models import JobType, SyncJob
from app.providers.base import WeChatProvider
from app.providers.registry import get_provider
from app.repositories import accounts as accounts_repo
from app.repositories import articles as articles_repo
from app.repositories import jobs as jobs_repo
from app.repositories import usage as usage_repo
from worker.tasks import sync_accounts, sync_articles, sync_metrics

logger = logging.getLogger("wechat_insight.worker")


async def run_job(
    session: Session, job: SyncJob, provider: WeChatProvider | None = None
) -> str:
    provider = provider or get_provider(job.provider)
    jobs_repo.start(session, job)
    session.flush()
    try:
        if job.job_type == JobType.SYNC_ACCOUNT:
            account = accounts_repo.get_by_id(session, job.target_id) if job.target_id else None
            if account is None:
                raise ProviderError("目标账号不存在。")
            await sync_accounts.sync_account(session, job, account, provider)
        elif job.job_type == JobType.SYNC_ARTICLES:
            account = accounts_repo.get_by_id(session, job.target_id) if job.target_id else None
            if account is None:
                raise ProviderError("目标账号不存在。")
            await sync_articles.sync_articles(session, job, account, provider)
        elif job.job_type == JobType.SYNC_METRICS:
            article = articles_repo.get_by_id(session, job.target_id) if job.target_id else None
            if article is None:
                raise ProviderError("目标文章不存在。")
            if getattr(provider, "supports_metrics", True):
                await sync_metrics.sync_metrics(session, job, article, provider)
        else:
            raise ProviderError(f"未知任务类型: {job.job_type}")

        jobs_repo.succeed(session, job)
        session.commit()
        return job.status
    except AppError as exc:
        usage_repo.log_usage(
            session,
            provider=getattr(provider, "name", job.provider),
            endpoint=job.job_type,
            success=False,
            job_id=job.id,
        )
        status = jobs_repo.fail(session, job, exc.code, exc.message)
        session.commit()
        logger.warning("job %s failed -> %s (%s)", job.id, status, exc.code)
        return status
    except Exception as exc:  # unexpected: still persist state, never crash the loop
        logger.exception("job %s crashed", job.id)
        usage_repo.log_usage(
            session,
            provider=getattr(provider, "name", job.provider),
            endpoint=job.job_type,
            success=False,
            job_id=job.id,
        )
        status = jobs_repo.fail(session, job, "INTERNAL_ERROR", str(exc))
        session.commit()
        return status


async def run_pending(
    session: Session,
    *,
    max_jobs: int = 50,
    provider: WeChatProvider | None = None,
    settings: Settings | None = None,
) -> int:
    """Process pending/retry jobs. Halted entirely once the budget is exceeded.

    Previously only C-tier jobs were skipped under budget pressure, so A/B jobs
    (most collection runs at B) kept spending past the daily cap. Now every paid
    call stops when the budget is blown — the budget check is re-evaluated before
    each job so a single batch cannot overshoot by 50 calls.
    """
    settings = settings or get_settings()

    def _blocked() -> bool:
        return usage_repo.budget_exceeded(
            session,
            daily_budget=settings.daily_budget_usd,
            monthly_budget=settings.monthly_budget_usd,
        )

    if _blocked():
        return 0

    processed = 0
    # Fresh work first.
    while processed < max_jobs:
        if _blocked():
            break
        job = jobs_repo.next_pending(session)
        if job is None:
            break
        await run_job(session, job, provider)
        processed += 1
    # Retries only once their backoff has elapsed; never straight after failing.
    for job in jobs_repo.due_retries(session, limit=max_jobs - processed):
        if _blocked():
            break
        await run_job(session, job, provider)
        processed += 1
    return processed
