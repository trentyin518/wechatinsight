"""Selection list (选号清单) API schemas."""

from __future__ import annotations

from datetime import datetime

from app.schemas.accounts import AccountOut
from app.schemas.common import ORMModel


class SelectionItemOut(ORMModel):
    account: AccountOut
    added_at: datetime


class SelectionListResponse(ORMModel):
    items: list[SelectionItemOut]
    total: int


class SelectionAddRequest(ORMModel):
    account_id: int


class SelectionState(ORMModel):
    account_id: int
    selected: bool
    total: int
