"""Job execution engine: dispatch, state machine, usage accounting."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ProviderError
from app.db.models import JobStatus, JobType, SyncJob, WechatAccount, WechatArticle
from app.db.session import SessionLocal
from app.providers.base import WeChatProvider
from app.providers.registry import get_provider
from app.repositories import accounts as accounts_repo
from app.repositories import articles as articles_repo
from app.repositories import jobs as jobs_repo
from app.repositories import usage as usage_repo
from worker.tasks import sync_accounts, sync_articles, sync_metrics

logger = logging.getLogger("wechat_insight.worker")


async def run_job(
    session: Session,
    job: SyncJob,
    provider: WeChatProvider | None = None,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    provider = provider or get_provider(job.provider)
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
            await sync_articles.sync_articles(
                session,
                job,
                account,
                provider,
                settings=settings,
            )
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


def _concurrency(settings: Settings) -> int:
    return max(1, int(getattr(settings, "metrics_concurrency", 1) or 1))


def _claim_batch(
    session: Session,
    limit: int,
    *,
    job_type: str | None = None,
    exclude_types: set[str] | None = None,
) -> list[SyncJob]:
    """Atomically claim up to ``limit`` PENDING jobs (-> RUNNING)."""
    claimed: list[SyncJob] = []
    while len(claimed) < limit:
        job = jobs_repo.next_pending(session, job_type=job_type, exclude_types=exclude_types)
        if job is None:
            break
        if jobs_repo.start(session, job):
            claimed.append(job)
        else:
            session.commit()
    if claimed:
        # Persist the RUNNING claims so each per-task session (and any other
        # consumer) sees them as claimed before we fan out.
        session.commit()
    return claimed


def _account_group(jobs: list[SyncJob], session: Session) -> dict[int | None, list[int]]:
    """Group metrics job ids by account so per-account work stays sequential.

    Concurrent writers to the same WechatAccount row (each metrics job recomputes
    the account's aggregates) would thrash/lock; grouping keeps one account's
    metrics on one worker while different accounts run in parallel.
    """
    article_ids = [j.target_id for j in jobs if j.target_id is not None]
    account_of: dict[int, int] = {}
    if article_ids:
        rows = session.execute(
            select(WechatArticle.id, WechatArticle.account_id).where(
                WechatArticle.id.in_(article_ids)
            )
        ).all()
        account_of = {article_id: account_id for article_id, account_id in rows}

    groups: dict[int | None, list[int]] = {}
    for job in jobs:
        account_id = account_of.get(job.target_id) if job.target_id is not None else None
        groups.setdefault(account_id, []).append(job.id)
    return groups


async def _run_target_jobs_concurrent(
    jobs: list[SyncJob],
    provider: WeChatProvider | None,
    settings: Settings,
) -> int:
    """Run non-metrics jobs concurrently, grouped by account.

    Article/account jobs each target a distinct account; grouping by target keeps
    two jobs for the same account on one worker (no same-row write races) while
    different accounts run in parallel. Each job uses its own Session.
    """
    if not jobs:
        return 0

    groups: dict[int | None, list[int]] = {}
    for job in jobs:
        groups.setdefault(job.target_id, []).append(job.id)
    sem = asyncio.Semaphore(_concurrency(settings))

    async def _run_group(job_ids: list[int]) -> int:
        done = 0
        async with sem:  # bound concurrent provider calls
            task_session = SessionLocal()
            try:
                for job_id in job_ids:
                    if usage_repo.budget_exceeded(
                        task_session,
                        daily_budget=settings.daily_budget_usd,
                        monthly_budget=settings.monthly_budget_usd,
                    ):
                        break
                    job = jobs_repo.get(task_session, job_id)
                    if job is None or job.status != JobStatus.RUNNING:
                        continue
                    await run_job(task_session, job, provider, settings)
                    done += 1
            except Exception:  # never let one account's group sink the others
                logger.exception("sync job group crashed")
                task_session.rollback()
            finally:
                task_session.close()
        return done

    results = await asyncio.gather(
        *(_run_group(ids) for ids in groups.values()), return_exceptions=True
    )
    return sum(r for r in results if isinstance(r, int))


async def _run_metrics_concurrent(
    jobs: list[SyncJob],
    session: Session,
    provider: WeChatProvider | None,
    settings: Settings,
) -> int:
    """Run a batch of metrics jobs concurrently, per account, bounded globally.

    Each job uses its own Session, so the shared ``session`` is never touched
    concurrently. The semaphore bounds concurrent provider calls by
    ``metrics_concurrency``. After an account's whole metric batch lands, its
    aggregates are recomputed **once** (rather than per article) — that's what
    makes intra-account concurrency safe and cheap.
    """
    if not jobs:
        return 0

    groups = _account_group(jobs, session)  # {account_id | None: [job_id, ...]}
    sem = asyncio.Semaphore(_concurrency(settings))

    def _over_budget(s: Session) -> bool:
        return usage_repo.budget_exceeded(
            s,
            daily_budget=settings.daily_budget_usd,
            monthly_budget=settings.monthly_budget_usd,
        )

    async def _run_one(job_id: int) -> int:
        async with sem:  # bound concurrent provider calls
            task_session = SessionLocal()
            try:
                if _over_budget(task_session):
                    return 0
                job = jobs_repo.get(task_session, job_id)
                if job is None or job.status != JobStatus.RUNNING:
                    return 0
                await run_job(task_session, job, provider, settings)
                return 1
            except Exception:  # never let one job sink the batch
                logger.exception("metrics job %s crashed", job_id)
                task_session.rollback()
                return 0
            finally:
                task_session.close()

    async def _run_account(account_id: int | None, job_ids: list[int]) -> int:
        # Concurrency *inside* an account: all its metric calls go out together
        # (still globally bounded by the shared semaphore).
        results = await asyncio.gather(
            *(_run_one(j) for j in job_ids), return_exceptions=True
        )
        done = sum(r for r in results if isinstance(r, int))
        if account_id is not None and done:
            _refresh_account_aggregates(account_id)
        return done

    results = await asyncio.gather(
        *(_run_account(acc, ids) for acc, ids in groups.items()), return_exceptions=True
    )
    return sum(r for r in results if isinstance(r, int))


def _refresh_account_aggregates(account_id: int) -> None:
    """Recompute one account's derived averages in its own short transaction."""
    task_session = SessionLocal()
    try:
        account = task_session.get(WechatAccount, account_id)
        if account is not None:
            accounts_repo.refresh_derived_attributes(task_session, account)
            task_session.commit()
    except Exception:  # aggregate refresh is best-effort; metrics are already stored
        logger.exception("failed to refresh aggregates for account %s", account_id)
        task_session.rollback()
    finally:
        task_session.close()


async def run_pending(
    session: Session,
    *,
    max_jobs: int = 50,
    provider: WeChatProvider | None = None,
    settings: Settings | None = None,
) -> int:
    """Process pending/retry jobs. Halted entirely once the budget is exceeded.

    Each phase runs jobs concurrently, bounded by ``metrics_concurrency``:
    account/article jobs first (grouped by account), then metrics jobs (both
    across and within accounts). Every in-flight job uses its own Session, so the
    shared ``session`` is never used concurrently. Each account's derived
    aggregates are recomputed once after its metrics batch (not per article). The
    budget is re-checked before every job; at worst a concurrent batch can
    overshoot by up to ``metrics_concurrency`` paid calls.
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
    concurrency = _concurrency(settings)

    # Phase 1 — account/article jobs run concurrently across accounts; they
    # enqueue the metrics jobs fanned out below.
    while processed < max_jobs:
        if _blocked():
            break
        batch = _claim_batch(
            session,
            min(max_jobs - processed, concurrency * 2),
            exclude_types={JobType.SYNC_METRICS},
        )
        if not batch:
            break
        processed += await _run_target_jobs_concurrent(batch, provider, settings)

    # Phase 2 — metrics jobs run concurrently, bounded per account.
    while processed < max_jobs:
        if _blocked():
            break
        batch = _claim_batch(
            session,
            min(max_jobs - processed, concurrency * 2),
            job_type=JobType.SYNC_METRICS,
        )
        if not batch:
            break
        processed += await _run_metrics_concurrent(batch, session, provider, settings)

    # Phase 3 — retries only once their backoff has elapsed (kept sequential).
    for job in jobs_repo.due_retries(session, limit=max_jobs - processed):
        if _blocked():
            break
        if not jobs_repo.start(session, job):
            session.commit()
            continue
        await run_job(session, job, provider, settings)
        processed += 1
    return processed
