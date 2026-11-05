"""Sync-job persistence and state-machine transitions.

State machine:
    PENDING -> RUNNING -> SUCCESS | RETRY | FAILED
    RETRY   -> RUNNING
``SUCCESS`` and ``FAILED`` are terminal.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import JobStatus, SyncJob

_ALLOWED: dict[str, set[str]] = {
    JobStatus.PENDING: {JobStatus.RUNNING},
    JobStatus.RUNNING: {JobStatus.SUCCESS, JobStatus.RETRY, JobStatus.FAILED},
    JobStatus.RETRY: {JobStatus.RUNNING},
    JobStatus.SUCCESS: set(),
    JobStatus.FAILED: set(),
}


class InvalidTransition(ValueError):
    pass


def available_transitions(status: str) -> set[str]:
    return set(_ALLOWED.get(status, set()))


def transition(job: SyncJob, new_status: str) -> None:
    if new_status not in JobStatus.ALL:
        raise InvalidTransition(f"unknown status {new_status}")
    if new_status not in _ALLOWED.get(job.status, set()):
        raise InvalidTransition(f"cannot go {job.status} -> {new_status}")
    now = datetime.now(timezone.utc)
    job.status = new_status
    if new_status == JobStatus.RUNNING:
        job.started_at = job.started_at or now
    if new_status in {JobStatus.SUCCESS, JobStatus.FAILED}:
        job.finished_at = now


def create_job(
    session: Session,
    *,
    job_type: str,
    target_type: str,
    provider: str,
    target_id: int | None = None,
    priority: str = "B",
    max_retries: int = 3,
    cursor: str | None = None,
) -> SyncJob:
    job = SyncJob(
        job_type=job_type,
        target_type=target_type,
        target_id=target_id,
        provider=provider,
        priority=priority,
        max_retries=max_retries,
        cursor=cursor,
        status=JobStatus.PENDING,
    )
    session.add(job)
    session.flush()
    return job


def get(session: Session, job_id: int) -> SyncJob | None:
    return session.get(SyncJob, job_id)


def next_pending(
    session: Session,
    job_type: str | None = None,
    *,
    exclude_priorities: set[str] | None = None,
) -> SyncJob | None:
    """Pick the highest-priority PENDING/RETRY job (A before B before C)."""
    stmt = select(SyncJob).where(SyncJob.status.in_([JobStatus.PENDING, JobStatus.RETRY]))
    if job_type is not None:
        stmt = stmt.where(SyncJob.job_type == job_type)
    if exclude_priorities:
        stmt = stmt.where(SyncJob.priority.notin_(exclude_priorities))
    stmt = stmt.order_by(SyncJob.priority.asc(), SyncJob.id.asc()).limit(1)
    return session.scalar(stmt)


def start(session: Session, job: SyncJob) -> None:
    transition(job, JobStatus.RUNNING)
    session.flush()


def succeed(session: Session, job: SyncJob) -> None:
    transition(job, JobStatus.SUCCESS)
    session.flush()


def fail(session: Session, job: SyncJob, error_code: str, error_message: str | None = None) -> str:
    """Record a failure; go to RETRY until retries exhausted, else FAILED."""
    job.retry_count += 1
    job.error_code = error_code
    job.error_message = (error_message or "")[:1000] or None
    target = JobStatus.FAILED if job.retry_count >= job.max_retries else JobStatus.RETRY
    transition(job, target)
    if target == JobStatus.RETRY:
        # Allow the retried run to start again.
        job.started_at = None
    session.flush()
    return target


def add_usage(session: Session, job: SyncJob, *, api_calls: int, estimated_cost: float) -> None:
    job.api_calls += api_calls
    job.estimated_cost = round(job.estimated_cost + estimated_cost, 6)
    session.flush()


def set_cursor(session: Session, job: SyncJob, cursor: str | None) -> None:
    job.cursor = cursor
    session.flush()
