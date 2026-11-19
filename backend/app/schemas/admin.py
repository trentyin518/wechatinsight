"""Admin usage / budget overview schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UsageLogItem(BaseModel):
    request_time: datetime
    provider: str
    endpoint: str
    success: bool
    estimated_cost: float


class UsageOverview(BaseModel):
    # Live balance from the provider (None if unavailable / provider has none).
    balance_usd: float | None
    plan: str | None
    # Estimated spend from our own usage log.
    daily_cost_usd: float
    monthly_cost_usd: float
    daily_budget_usd: float
    monthly_budget_usd: float
    today_calls: int
    # Whether any *background* paid work is currently allowed to run.
    collection_enabled: bool
    search_retry_enabled: bool
    # Cost-safety flags for the dashboard banner.
    over_daily_budget: bool
    over_monthly_budget: bool
    recent: list[UsageLogItem]


class SyncFailureReason(BaseModel):
    error_code: str | None
    count: int


class SyncFailedJob(BaseModel):
    id: int
    job_type: str
    target_type: str
    target_id: int | None
    error_code: str | None
    error_message: str | None
    updated_at: datetime


class JobTypeBreakdown(BaseModel):
    """Per-task-type status counts (文章同步 vs 指标获取 vs 账号同步)."""

    job_type: str
    total: int
    status_counts: dict[str, int]


class SyncHealth(BaseModel):
    """At-a-glance health of the sync-job queue (catches "nothing consuming")."""

    status_counts: dict[str, int]
    total_jobs: int
    # Stuck-queue signal: how many jobs are queued and how old the oldest is.
    pending_count: int
    pending_oldest_at: datetime | None
    pending_oldest_age_seconds: int | None
    # Metrics backlog + the threshold above which a manual drain self-throttles.
    metrics_pending: int
    metrics_throttle_threshold: int
    # Failure breakdown (top reasons) + the most recent failures for triage.
    failed_reasons: list[SyncFailureReason]
    recent_failed: list[SyncFailedJob]
    # Per-task-type split so backlog is attributable (articles vs metrics).
    by_type: list[JobTypeBreakdown]
    # Throughput in the last 24h, to tell "idle" from "broken".
    success_24h: int
    failed_24h: int
    # Human hint when the queue looks stuck (e.g. no worker running).
    worker_hint: str | None


class SyncDrainResult(BaseModel):
    """Response for a manual "drain the backlog" trigger."""

    scheduled: bool
    pending: int
    metrics_pending: int
    max_jobs: int
    throttled: bool
    message: str
