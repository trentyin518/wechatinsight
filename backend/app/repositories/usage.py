"""API usage + cost logging and budget checks."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ApiUsageLog

# Per-call cost model. Qovia docs/examples bill ~$0.005 per raw call; refine
# once real invoices are compared. Trials currently return billed=false.
DEFAULT_UNIT_COST_USD = 0.005


def log_usage(
    session: Session,
    *,
    provider: str,
    endpoint: str,
    success: bool,
    returned_items: int = 0,
    request_units: int = 1,
    estimated_cost: float | None = None,
    currency: str = "USD",
    job_id: int | None = None,
) -> ApiUsageLog:
    if estimated_cost is None:
        estimated_cost = round(request_units * DEFAULT_UNIT_COST_USD, 6)
    log = ApiUsageLog(
        provider=provider,
        endpoint=endpoint,
        success=success,
        returned_items=returned_items,
        request_units=request_units,
        estimated_cost=estimated_cost,
        currency=currency,
        job_id=job_id,
    )
    session.add(log)
    session.flush()
    return log


def _sum_since(session: Session, start: datetime) -> float:
    total = session.scalar(
        select(func.coalesce(func.sum(ApiUsageLog.estimated_cost), 0.0)).where(
            ApiUsageLog.request_time >= start
        )
    )
    return float(total or 0.0)


def daily_cost(session: Session, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return _sum_since(session, start)


def monthly_cost(session: Session, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return _sum_since(session, start)


def budget_exceeded(
    session: Session, *, daily_budget: float, monthly_budget: float, now: datetime | None = None
) -> bool:
    return daily_cost(session, now) >= daily_budget or monthly_cost(session, now) >= monthly_budget
