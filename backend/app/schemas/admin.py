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
