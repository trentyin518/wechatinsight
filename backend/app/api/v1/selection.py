"""Selection list (选号清单) endpoints: add / remove / list per user."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.accounts import _account_out
from app.core.errors import NotFoundError
from app.db.models import User
from app.repositories import accounts as accounts_repo
from app.repositories import selection as selection_repo
from app.schemas.selection import (
    SelectionAddRequest,
    SelectionItemOut,
    SelectionListResponse,
    SelectionState,
)

router = APIRouter(tags=["selection"])


@router.get("/selection", response_model=SelectionListResponse)
def list_selection(
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SelectionListResponse:
    items = selection_repo.list_for_user(session, user.id)
    return SelectionListResponse(
        items=[
            SelectionItemOut(account=_account_out(item.account), added_at=item.created_at)
            for item in items
            if item.account is not None
        ],
        total=len(items),
    )


@router.post("/selection", response_model=SelectionState)
def add_selection(
    payload: SelectionAddRequest,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SelectionState:
    account = accounts_repo.get_by_id(session, payload.account_id)
    if account is None:
        raise NotFoundError("公众号不存在。")
    selection_repo.add(session, user.id, account.id)
    session.commit()
    total = selection_repo.count_for_user(session, user.id)
    return SelectionState(account_id=account.id, selected=True, total=total)


@router.delete("/selection/{account_id}", response_model=SelectionState)
def remove_selection(
    account_id: int,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SelectionState:
    selection_repo.remove(session, user.id, account_id)
    session.commit()
    total = selection_repo.count_for_user(session, user.id)
    return SelectionState(account_id=account_id, selected=False, total=total)
