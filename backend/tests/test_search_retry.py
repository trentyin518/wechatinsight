"""Search-retry queue: enqueue on busy, worker ingest, backoff/exhaust."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.errors import DataSourceBusy
from app.db.models import SearchRetryQueue, WechatAccount
from app.providers.base import ProviderAccount, SearchPage
from app.repositories import search_retry_queue as retry_repo
from app.repositories.accounts import AccountFilters
from app.services import accounts as accounts_service
from app.services import search_retry


class _BusyProvider:
    name = "qovia"

    async def search_accounts(self, keyword, page=1, page_size=20):
        raise DataSourceBusy()


class _OkProvider:
    name = "qovia"

    async def search_accounts(self, keyword, page=1, page_size=20):
        return SearchPage(
            items=[
                ProviderAccount(
                    provider="qovia",
                    provider_account_id="mp-1",
                    name="汽车之家",
                    description="汽车资讯",
                )
            ],
            next_cursor=None,
        )


def test_busy_search_enqueues_retry(session):
    try:
        asyncio.run(
            accounts_service.search_accounts(
                session, "汽车之家", 1, 20, provider=_BusyProvider()
            )
        )
    except DataSourceBusy:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected DataSourceBusy")

    rows = session.scalars(select(SearchRetryQueue)).all()
    assert len(rows) == 1
    assert rows[0].keyword == "汽车之家"
    assert rows[0].status == "pending"
    assert rows[0].attempts == 0


def test_enqueue_is_idempotent(session):
    retry_repo.enqueue(session, "qovia", "汽车之家")
    retry_repo.enqueue(session, "qovia", "汽车之家")
    session.commit()
    rows = session.scalars(select(SearchRetryQueue)).all()
    assert len(rows) == 1


def test_busy_with_empty_filters_still_enqueues(session):
    # The API always passes an all-None AccountFilters; that must still queue.
    try:
        asyncio.run(
            accounts_service.search_accounts(
                session, "汽车之家", 1, 20,
                provider=_BusyProvider(), filters=AccountFilters(),
            )
        )
    except DataSourceBusy:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected DataSourceBusy")

    rows = session.scalars(select(SearchRetryQueue)).all()
    assert len(rows) == 1
    assert rows[0].keyword == "汽车之家"


def test_claim_is_single_winner(session):
    row = retry_repo.enqueue(session, "qovia", "独占号")
    session.commit()
    assert retry_repo.claim(session, row) is True
    assert row.status == "running"
    assert row.attempts == 1
    # A second processor cannot claim the same running row.
    assert retry_repo.claim(session, row) is False


def test_worker_ingests_and_caches_on_success(session):
    retry_repo.enqueue(session, "qovia", "汽车之家")
    session.commit()

    stats = asyncio.run(search_retry.run_search_retries(session, _OkProvider()))
    assert stats["retry_succeeded"] == 1

    row = session.scalars(select(SearchRetryQueue)).one()
    assert row.status == "succeeded"
    assert row.attempts == 1

    acc = session.scalars(
        select(WechatAccount).where(WechatAccount.name == "汽车之家")
    ).first()
    assert acc is not None

    # A follow-up search is answered from the local store (no provider call).
    result = asyncio.run(
        accounts_service.search_accounts(session, "汽车之家", 1, 20, provider=_BusyProvider())
    )
    assert result.total == 1


def test_worker_backs_off_on_busy(session):
    retry_repo.enqueue(session, "qovia", "合肥晚报")
    session.commit()
    now = datetime.now(timezone.utc)

    asyncio.run(search_retry.run_search_retries(session, _BusyProvider(), now=now))

    row = session.scalars(select(SearchRetryQueue)).one()
    assert row.status == "pending"
    assert row.attempts == 1
    nra = row.next_retry_at
    if nra.tzinfo is None:
        nra = nra.replace(tzinfo=timezone.utc)
    assert nra > now


def test_worker_exhausts_after_max_attempts(session):
    row = retry_repo.enqueue(session, "qovia", "某号", max_attempts=1)
    assert row is not None
    session.commit()

    asyncio.run(search_retry.run_search_retries(session, _BusyProvider()))

    row = session.scalars(select(SearchRetryQueue)).one()
    assert row.status == "exhausted"
    assert row.attempts == 1
