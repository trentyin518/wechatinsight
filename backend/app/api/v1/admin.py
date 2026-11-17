"""Admin-operations endpoints: usage & budget overview."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.core.config import get_settings
from app.db.models import ApiUsageLog, User
from app.providers.registry import get_provider
from app.repositories import usage as usage_repo
from app.schemas.admin import UsageLogItem, UsageOverview

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
