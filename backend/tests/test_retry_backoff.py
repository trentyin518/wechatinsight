"""Retry policy: failures back off instead of re-running in the same drain loop."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.db.models import JobStatus, JobType
from app.repositories import jobs as jobs_repo
from worker import engine


def test_retry_delay_grows_and_caps() -> None:
    assert jobs_repo.retry_delay(1) == timedelta(seconds=30)
    assert jobs_repo.retry_delay(2) == timedelta(seconds=60)
    assert jobs_repo.retry_delay(3) == timedelta(seconds=120)
    assert jobs_repo.retry_delay(20) == timedelta(seconds=jobs_repo.RETRY_MAX_SECONDS)


def test_failed_job_is_not_retried_in_same_cycle(session) -> None:
    job = jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_METRICS,
        target_type="article",
        target_id=1,
        provider="mock",
    )
    session.commit()

    class Boom:
        name = "mock"
        supports_metrics = True

        async def get_article_metrics(self, url):  # noqa: ANN001, ANN201
            from app.core.errors import DataSourceUnavailable

            raise DataSourceUnavailable()

    processed = asyncio.run(engine.run_pending(session, max_jobs=10, provider=Boom()))
    session.refresh(job)

    assert processed == 1
    assert job.status == JobStatus.RETRY
    assert job.retry_count == 1

    # Same cycle again: the backoff has not elapsed, so nothing is picked up.
    again = asyncio.run(engine.run_pending(session, max_jobs=10, provider=Boom()))
    assert again == 0


def test_retry_becomes_eligible_after_backoff(session) -> None:
    job = jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_METRICS,
        target_type="article",
        target_id=1,
        provider="mock",
    )
    session.commit()

    class Boom:
        name = "mock"
        supports_metrics = True

        async def get_article_metrics(self, url):  # noqa: ANN001, ANN201
            from app.core.errors import DataSourceUnavailable

            raise DataSourceUnavailable()

    asyncio.run(engine.run_pending(session, max_jobs=10, provider=Boom()))
    session.refresh(job)
    assert job.status == JobStatus.RETRY

    due = jobs_repo.due_retries(
        session, now=datetime.now(timezone.utc) + timedelta(minutes=10)
    )
    assert [j.id for j in due] == [job.id]


def test_failed_call_is_not_billed(session) -> None:
    from app.repositories import usage as usage_repo

    log = usage_repo.log_usage(
        session, provider="qovia", endpoint="SYNC_METRICS", success=False
    )
    assert log.estimated_cost == 0.0
