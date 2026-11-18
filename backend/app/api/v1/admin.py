"""Admin-operations endpoints: usage & budget overview."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.core.config import get_settings
from app.db.models import ApiUsageLog, JobStatus, SyncJob, User
from app.providers.registry import get_provider
from app.repositories import usage as usage_repo
from app.schemas.admin import (
    SyncDrainResult,
    SyncFailedJob,
    SyncFailureReason,
    SyncHealth,
    UsageLogItem,
    UsageOverview,
)
from app.services.demand_drain import drain_demand_jobs

router = APIRouter(prefix="/admin", tags=["admin"])


def _to_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


@router.get("/usage", response_model=UsageOverview)
async def usage_overview(
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> UsageOverview:
    settings = get_settings()
    now = datetime.now(timezone.utc)

    balance: float | None = None
    plan: str | None = None
    try:
        provider = get_provider()
        get_billing = getattr(provider, "get_billing", None)
        if callable(get_billing):
            billing = await get_billing()
            if billing:
                balance = _to_float(billing.get("balance_usd"))
                plan = billing.get("plan")
    except Exception:  # balance is best-effort; never fail the dashboard
        pass

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_calls = session.scalar(
        select(func.count()).select_from(ApiUsageLog).where(
            ApiUsageLog.request_time >= today_start
        )
    )
    recent_rows = session.scalars(
        select(ApiUsageLog).order_by(ApiUsageLog.id.desc()).limit(20)
    ).all()

    daily_cost = usage_repo.daily_cost(session, now)
    monthly_cost = usage_repo.monthly_cost(session, now)

    return UsageOverview(
        balance_usd=balance,
        plan=str(plan) if plan is not None else None,
        daily_cost_usd=round(daily_cost, 4),
        monthly_cost_usd=round(monthly_cost, 4),
        daily_budget_usd=settings.daily_budget_usd,
        monthly_budget_usd=settings.monthly_budget_usd,
        today_calls=int(today_calls or 0),
        collection_enabled=settings.collection_enabled,
        search_retry_enabled=settings.search_retry_enabled,
        over_daily_budget=daily_cost >= settings.daily_budget_usd,
        over_monthly_budget=monthly_cost >= settings.monthly_budget_usd,
        recent=[
            UsageLogItem(
                request_time=row.request_time,
                provider=row.provider,
                endpoint=row.endpoint,
                success=row.success,
                estimated_cost=row.estimated_cost,
            )
            for row in recent_rows
        ],
    )


@router.get("/sync", response_model=SyncHealth)
def sync_health(
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> SyncHealth:
    """Health of the sync-job queue, so "no data" is diagnosable at a glance."""
    now = datetime.now(timezone.utc)

    status_rows = session.execute(
        select(SyncJob.status, func.count(SyncJob.id)).group_by(SyncJob.status)
    ).all()
    status_counts = {status: int(count) for status, count in status_rows}
    total_jobs = sum(status_counts.values())

    pending_count = status_counts.get(JobStatus.PENDING, 0)
    oldest_pending = session.scalar(
        select(func.min(SyncJob.created_at)).where(SyncJob.status == JobStatus.PENDING)
    )
    if oldest_pending is not None and oldest_pending.tzinfo is None:
        oldest_pending = oldest_pending.replace(tzinfo=timezone.utc)
    pending_age = int((now - oldest_pending).total_seconds()) if oldest_pending else None

    reason_rows = session.execute(
        select(SyncJob.error_code, func.count(SyncJob.id))
        .where(SyncJob.status == JobStatus.FAILED)
        .group_by(SyncJob.error_code)
        .order_by(func.count(SyncJob.id).desc())
        .limit(8)
    ).all()
    failed_reasons = [
        SyncFailureReason(error_code=code, count=int(count)) for code, count in reason_rows
    ]

    recent_failed_rows = session.scalars(
        select(SyncJob)
        .where(SyncJob.status == JobStatus.FAILED)
        .order_by(SyncJob.updated_at.desc())
        .limit(12)
    ).all()
    recent_failed = [
        SyncFailedJob(
            id=row.id,
            job_type=row.job_type,
            target_type=row.target_type,
            target_id=row.target_id,
            error_code=row.error_code,
            error_message=row.error_message,
            updated_at=row.updated_at,
        )
        for row in recent_failed_rows
    ]

    since = now - timedelta(hours=24)
    success_24h = session.scalar(
        select(func.count(SyncJob.id)).where(
            SyncJob.status == JobStatus.SUCCESS, SyncJob.updated_at >= since
        )
    )
    failed_24h = session.scalar(
        select(func.count(SyncJob.id)).where(
            SyncJob.status == JobStatus.FAILED, SyncJob.updated_at >= since
        )
    )

    worker_hint: str | None = None
    if pending_count and pending_age is not None and pending_age > 600 and not success_24h:
        worker_hint = (
            "有排队任务且 24 小时内没有成功的同步：很可能没有 worker（或 API 内联消费）在运行。"
            "启动 backend/.venv/bin/python -m worker.main，或让页面搜索/详情触发一次。"
        )
    elif pending_count and pending_age is not None and pending_age > 600:
        worker_hint = "队列有任务排队超过 10 分钟，消费较慢，可检查 worker 是否在运行。"

    return SyncHealth(
        status_counts=status_counts,
        total_jobs=total_jobs,
        pending_count=pending_count,
        pending_oldest_at=oldest_pending,
        pending_oldest_age_seconds=pending_age,
        failed_reasons=failed_reasons,
        recent_failed=recent_failed,
        success_24h=int(success_24h or 0),
        failed_24h=int(failed_24h or 0),
        worker_hint=worker_hint,
    )


@router.post("/sync/drain", response_model=SyncDrainResult)
async def trigger_sync_drain(
    background: BackgroundTasks,
    max_jobs: int = Query(200, ge=1, le=2000, description="最多消费的任务数"),
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> SyncDrainResult:
    """Admin: kick off a bounded background drain of the PENDING backlog.

    Runs after the response is sent and claims jobs atomically, so it is safe to
    fire alongside a running worker. Cost is bounded by ``max_jobs`` and the
    normal budget guard inside ``run_pending``.
    """
    settings = get_settings()
    pending = int(
        session.scalar(
            select(func.count(SyncJob.id)).where(SyncJob.status == JobStatus.PENDING)
        )
        or 0
    )
    if pending <= 0:
        return SyncDrainResult(
            scheduled=False, pending=0, max_jobs=max_jobs, message="没有排队任务。"
        )

    cap = min(max_jobs, pending)
    background.add_task(drain_demand_jobs, settings, cap)
    return SyncDrainResult(
        scheduled=True,
        pending=pending,
        max_jobs=cap,
        message=f"已在后台开始消费，最多处理 {cap} 个任务（每个调用约 $0.005）。",
    )
