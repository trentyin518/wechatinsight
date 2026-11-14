"""Homepage overview: real aggregate coverage + recently updated accounts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.accounts import AccountOut


class OverviewResponse(BaseModel):
    accounts_count: int
    articles_count: int
    metrics_count: int
    providers_count: int
    last_updated_at: datetime | None = None
    recent_accounts: list[AccountOut] = []
