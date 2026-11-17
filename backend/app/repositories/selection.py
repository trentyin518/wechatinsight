"""Selection list (选号清单) persistence."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import SelectionItem


def list_for_user(session: Session, user_id: int) -> list[SelectionItem]:
    stmt = (
        select(SelectionItem)
        .where(SelectionItem.user_id == user_id)
        .order_by(SelectionItem.created_at.desc(), SelectionItem.id.desc())
    )
    return list(session.scalars(stmt))


def count_for_user(session: Session, user_id: int) -> int:
    return (
        session.scalar(
            select(func.count(SelectionItem.id)).where(SelectionItem.user_id == user_id)
        )
        or 0
    )


def get(session: Session, user_id: int, account_id: int) -> SelectionItem | None:
    return session.scalar(
        select(SelectionItem).where(
            SelectionItem.user_id == user_id,
            SelectionItem.account_id == account_id,
        )
    )


def add(session: Session, user_id: int, account_id: int) -> SelectionItem:
    existing = get(session, user_id, account_id)
    if existing is not None:
        return existing
    item = SelectionItem(user_id=user_id, account_id=account_id)
    session.add(item)
    session.flush()
    return item


def remove(session: Session, user_id: int, account_id: int) -> bool:
    item = get(session, user_id, account_id)
    if item is None:
        return False
    session.delete(item)
    session.flush()
    return True
