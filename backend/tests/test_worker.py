"""Worker end-to-end: sync cycle, idempotency and cursor resume."""

from __future__ import annotations

import asyncio

from app.db.models import (
    ApiUsageLog,
    ArticleMetric,
    JobStatus,
    JobType,
    SyncJob,
    WechatArticle,
)
from app.providers.base import ProviderAccount, ProviderArticle
from app.providers.mock import MockProvider
from app.repositories import accounts as accounts_repo
from app.repositories import articles as articles_repo
from app.repositories import jobs as jobs_repo
from worker import engine, scheduler
from worker.tasks import sync_articles


def _seed(session):
    accounts_repo.upsert_from_provider(
        session,
        ProviderAccount(
            provider="mock",
            provider_account_id="mock-1001",
            name="示例科技观察",
            wechat_id="mock_tech",
        ),
    )
    session.commit()


def _run_cycle(session):
    scheduler.enqueue_due_work(session)
    session.commit()
    return asyncio.run(engine.run_pending(session, provider=MockProvider()))


def test_worker_cycle_populates_articles_metrics_usage(session):
    _seed(session)
    _run_cycle(session)  # account + articles
    _run_cycle(session)  # metrics for now-existing articles

    assert session.query(WechatArticle).count() >= 5
    assert session.query(ArticleMetric).count() >= 5
    assert session.query(ApiUsageLog).count() > 0
    assert (
        session.query(SyncJob).filter(SyncJob.status == JobStatus.FAILED).count() == 0
    )


def test_running_again_does_not_duplicate_articles(session):
    _seed(session)
    _run_cycle(session)
    first = session.query(WechatArticle).count()
    _run_cycle(session)
    _run_cycle(session)
    assert session.query(WechatArticle).count() == first


def test_cursor_resume_across_pages(session):
    _seed(session)
    account = session.query(accounts_repo.WechatAccount).first()
    job = jobs_repo.create_job(
        session,
        job_type=JobType.SYNC_ARTICLES,
        target_type="account",
        target_id=account.id,
        provider="mock",
    )
    session.commit()

    provider = MockProvider()
    asyncio.run(
        sync_articles.sync_articles(session, job, account, provider, max_pages=1, page_size=2)
    )
    assert job.cursor == "2"
    assert session.query(WechatArticle).count() == 2

    asyncio.run(
        sync_articles.sync_articles(session, job, account, provider, max_pages=10, page_size=2)
    )
    assert job.cursor is None
    assert session.query(WechatArticle).count() == 5


def test_metrics_jobs_skipped_for_provider_without_metrics(session):
    from app.providers.registry import register_provider

    class _NoMetricsProvider:
        name = "nometrics"
        supports_metrics = False

    register_provider("nometrics", lambda _settings: _NoMetricsProvider())

    account = accounts_repo.upsert_from_provider(
        session,
        ProviderAccount(provider="nometrics", provider_account_id="gh_none", name="账号X"),
    )
    session.commit()
    articles_repo.upsert_from_provider(
        session,
        account.id,
        ProviderArticle(
            provider="nometrics", title="t", url="https://mp.weixin.qq.com/s?__biz=gh_none&mid=1"
        ),
    )
    session.commit()

    scheduler.enqueue_due_work(session)
    session.commit()

    metrics_jobs = session.query(SyncJob).filter(SyncJob.job_type == JobType.SYNC_METRICS).count()
    assert metrics_jobs == 0


def test_metrics_jobs_enqueued_for_qovia(session):
    account = accounts_repo.upsert_from_provider(
        session,
        ProviderAccount(provider="qovia", provider_account_id="gh_q", name="账号Q"),
    )
    session.commit()
    articles_repo.upsert_from_provider(
        session,
        account.id,
        ProviderArticle(
            provider="qovia", title="t", url="https://mp.weixin.qq.com/s?__biz=gh_q&mid=1"
        ),
    )
    session.commit()

    scheduler.enqueue_due_work(session)
    session.commit()

    metrics_jobs = session.query(SyncJob).filter(SyncJob.job_type == JobType.SYNC_METRICS).count()
    assert metrics_jobs == 1
