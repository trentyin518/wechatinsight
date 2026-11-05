"""Job state machine + budget-aware scheduling."""

from __future__ import annotations

import asyncio

import pytest

from app.db.models import JobStatus, JobType, Priority, SyncJob
from app.repositories import jobs as jobs_repo
from app.repositories import usage as usage_repo
from app.providers.base import ProviderAccount
from app.repositories import accounts as accounts_repo
from worker import engine


def test_valid_transitions():
    job = SyncJob(status=JobStatus.PENDING)
    jobs_repo.transition(job, JobStatus.RUNNING)
    assert job.status == JobStatus.RUNNING
    jobs_repo.transition(job, JobStatus.SUCCESS)
    assert job.status == JobStatus.SUCCESS


def test_invalid_transition_rejected():
    job = SyncJob(status=JobStatus.SUCCESS)
    with pytest.raises(jobs_repo.InvalidTransition):
        jobs_repo.transition(job, JobStatus.RUNNING)


def test_fail_retries_then_fails(session):
    job = jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_METRICS,
        target_type="article",
        target_id=1,
        provider="mock",
        max_retries=2,
    )
    session.commit()

    jobs_repo.start(session, job)
    assert jobs_repo.fail(session, job, "X") == JobStatus.RETRY
    jobs_repo.start(session, job)
    assert jobs_repo.fail(session, job, "X") == JobStatus.FAILED
    assert job.error_code == "X"


def test_budget_exceeded_skips_c_priority(session):
    account = accounts_repo.upsert_from_provider(
        session,
        ProviderAccount(
            provider="mock", provider_account_id="mock-1001", name="示例", wechat_id="mock_tech"
        ),
    )
    session.commit()

    job = jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_ACCOUNT,
        target_type="account",
        target_id=account.id,
        provider="mock",
        priority=Priority.C,
    )
    session.commit()

    # Push spend above the daily budget.
    usage_repo.log_usage(session, provider="mock", endpoint="x", success=True, estimated_cost=999)
    session.commit()

    processed = asyncio.run(
        engine.run_pending(session, max_jobs=10, settings=_settings_with_budget(5.0))
    )
    session.refresh(job)
    assert processed == 0
    assert job.status == JobStatus.PENDING


def _settings_with_budget(daily: float):
    from app.core.config import get_settings

    base = get_settings()
    return base.__class__(
        app_env=base.app_env,
        database_url=base.database_url,
        default_provider=base.default_provider,
        cors_origins=base.cors_origins,
        daily_budget_usd=daily,
        monthly_budget_usd=base.monthly_budget_usd,
        allow_cold_start_search=base.allow_cold_start_search,
        search_rate_limit_per_minute=base.search_rate_limit_per_minute,
        qovia_api_key=base.qovia_api_key,
        qovia_base_url=base.qovia_base_url,
        xmedi_api_key=base.xmedi_api_key,
        xmedi_base_url=base.xmedi_base_url,
    )


def test_next_pending_prefers_higher_priority(session):
    low = jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_METRICS,
        target_type="article",
        target_id=1,
        provider="mock",
        priority=Priority.C,
    )
    high = jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_METRICS,
        target_type="article",
        target_id=2,
        provider="mock",
        priority=Priority.A,
    )
    session.commit()

    picked = jobs_repo.next_pending(session)
    assert picked is not None
    assert picked.id == high.id
    assert picked.id != low.id
