"""Demand-driven, search-triggered collection.

Covers the cost-safety contract:
- A search only enqueues enrichment for the accounts on the *visible* page.
- Repeating an identical search does not pay twice (active-job dedup + TTL).
- On-demand sync can be switched off entirely.
- Once the worker drains the jobs, real derived averages appear and the account
  is not re-enqueued within the TTL.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.models import ApiUsageLog, ArticleMetric, JobStatus, JobType, SyncJob, WechatArticle
from app.providers.base import ProviderAccount
from app.providers.mock import MockProvider
from app.repositories import accounts as accounts_repo
from app.repositories import jobs as jobs_repo
from app.services import accounts as accounts_service
from app.services import collection as collection_service
from worker import engine


def _seed_accounts(session, count: int, *, provider: str = "mock") -> None:
    for i in range(count):
        accounts_repo.upsert_from_provider(
            session,
            ProviderAccount(
                provider=provider,
                provider_account_id=f"{provider}-{i:03d}",
                name=f"测试号{i:03d}",
                wechat_id=f"test_{i:03d}",
            ),
        )
    session.commit()


def _article_jobs(session) -> int:
    return session.query(SyncJob).filter(SyncJob.job_type == JobType.SYNC_ARTICLES).count()


def _settings(**overrides):
    base = get_settings()
    data = dict(base.__dict__)
    data.update(overrides)
    return base.__class__(**data)


async def test_search_enqueues_only_visible_page(session):
    _seed_accounts(session, 25)

    page1 = await accounts_service.search_accounts(session, "测试号", 1, 20)
    assert page1.total == 25
    assert len(page1.items) == 20
    assert _article_jobs(session) == 20  # only the 20 accounts on page 1

    page2 = await accounts_service.search_accounts(session, "测试号", 2, 20)
    assert len(page2.items) == 5
    # Page 2 adds exactly its 5 accounts; we never swept all 25 up front.
    assert _article_jobs(session) == 25


async def test_repeated_search_does_not_duplicate_jobs(session):
    _seed_accounts(session, 5)

    await accounts_service.search_accounts(session, "测试号", 1, 20)
    first = _article_jobs(session)
    await accounts_service.search_accounts(session, "测试号", 1, 20)
    assert _article_jobs(session) == first  # identical search, no new spend


async def test_on_demand_disabled_enqueues_nothing(session):
    _seed_accounts(session, 3)
    settings = _settings(on_demand_sync_enabled=False)

    await accounts_service.search_accounts(session, "测试号", 1, 20, settings=settings)
    assert _article_jobs(session) == 0


async def test_demand_sync_populates_derived_and_is_not_reenqueued(session):
    _seed_accounts(session, 1, provider="mock")
    account = session.query(accounts_repo.WechatAccount).one()

    created = collection_service.enqueue_accounts_for_sync(session, [account])
    assert created == 1
    session.commit()

    # Cycle 1: articles; cycle 2: metrics chained by sync_articles.
    await engine.run_pending(session, provider=MockProvider())
    await engine.run_pending(session, provider=MockProvider())

    session.refresh(account)
    assert account.article_count == 5
    assert account.avg_read is not None
    assert account.last_synced_at is not None
    assert session.query(WechatArticle).count() == 5
    assert session.query(ArticleMetric).count() >= 1
    assert session.query(ApiUsageLog).count() > 0

    # Within the TTL the same account is not re-enqueued (no repeat spend).
    assert collection_service.enqueue_accounts_for_sync(session, [account]) == 0


async def test_metrics_calls_are_bounded_per_account(session):
    _seed_accounts(session, 1, provider="mock")
    account = session.query(accounts_repo.WechatAccount).one()
    # Push articles in directly (avoid an articles job), then schedule metrics.
    from app.providers.base import ProviderArticle
    from app.repositories import articles as articles_repo

    for i in range(15):
        articles_repo.upsert_from_provider(
            session,
            account.id,
            ProviderArticle(
                provider="mock",
                title=f"文章{i}",
                url=f"https://example.com/mock/metrics-{i}",
            ),
        )
    session.commit()

    settings = _settings(metrics_per_account_limit=10)
    created = collection_service.enqueue_metrics_for_account(session, account, settings=settings)
    assert created == 10  # capped at the configured limit, not all 15


async def test_pending_collection_status_reflects_queued_jobs(session):
    _seed_accounts(session, 2)
    a1, a2 = session.query(accounts_repo.WechatAccount).order_by(accounts_repo.WechatAccount.id).all()

    assert accounts_repo.ids_with_pending_collection(session, [a1.id, a2.id]) == set()

    collection_service.enqueue_accounts_for_sync(session, [a1])
    collecting = accounts_repo.ids_with_pending_collection(session, [a1.id, a2.id])
    assert a1.id in collecting
    assert a2.id not in collecting


async def test_start_is_atomic_claim(session):
    from app.db.session import SessionLocal
    from app.repositories import jobs as jobs_repo

    job = jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_METRICS,
        target_type="article",
        target_id=1,
        provider="mock",
    )
    session.commit()

    # First claim wins...
    assert jobs_repo.start(session, job) is True
    session.commit()  # persist RUNNING and release SQLite's write lock

    other = SessionLocal()
    try:
        # ...a concurrent consumer claiming the same job is rejected, so the
        # job is never processed (or billed) twice.
        other_job = other.get(SyncJob, job.id)
        assert jobs_repo.start(other, other_job) is False
    finally:
        other.close()


async def test_inline_drain_processes_demand_jobs_without_worker():
    from app.db.session import SessionLocal
    from app.services.demand_drain import drain_demand_jobs

    setup = SessionLocal()
    try:
        _seed_accounts(setup, 1)
        account = setup.query(accounts_repo.WechatAccount).one()
        assert collection_service.enqueue_accounts_for_sync(setup, [account]) == 1
        setup.commit()
    finally:
        setup.close()

    processed = await drain_demand_jobs(_settings())
    assert processed >= 1

    check = SessionLocal()
    try:
        account = check.query(accounts_repo.WechatAccount).one()
        assert account.article_count and account.article_count > 0
        assert account.avg_read is not None
        assert account.last_synced_at is not None
        # Nothing left collecting once the drain has run.
        assert accounts_repo.ids_with_pending_collection(check, [account.id]) == set()
    finally:
        check.close()


async def test_collection_states_classify_accounts(session):
    _seed_accounts(session, 5)
    ordered = (
        session.query(accounts_repo.WechatAccount)
        .order_by(accounts_repo.WechatAccount.id)
        .all()
    )
    collected, empty, failed, collecting, idle = ordered

    collected.article_count = 5  # has data
    empty.last_synced_at = datetime.now(timezone.utc)  # synced but zero articles

    failed_job = jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_ARTICLES,
        target_type="account",
        target_id=failed.id,
        provider="qovia",
    )
    failed_job.status = JobStatus.FAILED
    failed_job.error_code = "DATA_SOURCE_BILLING"

    jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_ARTICLES,
        target_type="account",
        target_id=collecting.id,
        provider="qovia",
    )
    session.commit()

    states = accounts_repo.collection_states(
        session, [collected, empty, failed, collecting, idle]
    )
    assert states[collected.id].state == "collected"
    assert states[empty.id].state == "empty"
    assert states[failed.id].state == "failed"
    assert states[failed.id].error_code == "DATA_SOURCE_BILLING"
    assert states[collecting.id].state == "collecting"
    assert states[idle.id].state == "idle"

