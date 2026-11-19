"""Metrics jobs run concurrently across accounts, bounded by metrics_concurrency."""

from __future__ import annotations

import asyncio
import dataclasses

from app.core.config import get_settings
from app.db.models import JobType
from app.providers.base import (
    ArticlePage,
    ProviderAccount,
    ProviderArticle,
    ProviderMetrics,
)
from app.repositories import accounts as accounts_repo
from app.repositories import articles as articles_repo
from app.repositories import jobs as jobs_repo
from worker import engine


class _ConcurrencyTracker:
    name = "mock"
    supports_metrics = True

    def __init__(self) -> None:
        self.inflight = 0
        self.max_inflight = 0

    async def get_article_metrics(self, url):  # noqa: ANN001, ANN201
        self.inflight += 1
        self.max_inflight = max(self.max_inflight, self.inflight)
        try:
            await asyncio.sleep(0.02)
            return ProviderMetrics(provider="mock", read_count=1)
        finally:
            self.inflight -= 1


def test_metrics_run_concurrently_and_stay_bounded(session):
    missing = "https://mp.weixin.qq.com/s?__biz=x"
    article_ids = []
    for i in range(10):  # 10 accounts -> 10 independent metrics jobs
        account = accounts_repo.upsert_from_provider(
            session,
            ProviderAccount(
                provider="mock",
                provider_account_id=f"conc-{i}",
                name=f"并发号{i}",
                wechat_id=f"conc_{i}",
            ),
        )
        article = articles_repo.upsert_from_provider(
            session,
            account.id,
            ProviderArticle(provider="mock", title="t", url=f"{missing}&mid={i}"),
        )
        article_ids.append(article.id)
        jobs_repo.create_job(
            session,
            job_type=JobType.SYNC_METRICS,
            target_type="article",
            target_id=article.id,
            provider="mock",
        )
    session.commit()

    settings = dataclasses.replace(get_settings(), metrics_concurrency=4)
    tracker = _ConcurrencyTracker()
    processed = asyncio.run(
        engine.run_pending(session, max_jobs=50, provider=tracker, settings=settings)
    )

    assert processed == 10
    # Concurrency actually happened (not serial) but never exceeded the cap.
    assert tracker.max_inflight >= 2
    assert tracker.max_inflight <= 4


def test_intra_account_metrics_run_concurrently(session):
    # A single account with 8 articles: all metrics belong to the same account,
    # which is exactly the case the old per-article aggregate recompute blocked.
    account = accounts_repo.upsert_from_provider(
        session,
        ProviderAccount(
            provider="mock",
            provider_account_id="solo",
            name="单账号",
            wechat_id="solo",
        ),
    )
    for i in range(8):
        article = articles_repo.upsert_from_provider(
            session,
            account.id,
            ProviderArticle(provider="mock", title="t", url=f"https://x/solo/{i}"),
        )
        jobs_repo.create_job(
            session,
            job_type=JobType.SYNC_METRICS,
            target_type="article",
            target_id=article.id,
            provider="mock",
        )
    session.commit()

    settings = dataclasses.replace(get_settings(), metrics_concurrency=4)
    tracker = _ConcurrencyTracker()
    processed = asyncio.run(
        engine.run_pending(session, max_jobs=50, provider=tracker, settings=settings)
    )

    assert processed == 8
    # Concurrency happens *inside* one account now, still bounded by the cap.
    assert tracker.max_inflight >= 2
    assert tracker.max_inflight <= 4
    # Aggregates are recomputed once for the account and reflect the snapshots.
    session.refresh(account)
    assert account.article_count == 8
    assert account.avg_read == 1.0


class _ArticlesTracker:
    name = "mock"
    supports_metrics = False

    def __init__(self) -> None:
        self.inflight = 0
        self.max_inflight = 0

    async def get_articles(
        self,
        provider_account_id,
        cursor=None,
        page_size=20,
        *,
        account_name=None,
    ):  # noqa: ANN001, ANN201
        self.inflight += 1
        self.max_inflight = max(self.max_inflight, self.inflight)
        try:
            await asyncio.sleep(0.02)
            return ArticlePage(
                items=[
                    ProviderArticle(
                        provider="mock",
                        title="t",
                        url=f"https://x/{provider_account_id}",
                    )
                ],
                next_cursor=None,
            )
        finally:
            self.inflight -= 1


def test_article_jobs_run_concurrently_across_accounts(session):
    for i in range(10):  # 10 accounts -> 10 independent article-sync jobs
        account = accounts_repo.upsert_from_provider(
            session,
            ProviderAccount(
                provider="mock",
                provider_account_id=f"art-{i}",
                name=f"文章号{i}",
                wechat_id=f"art_{i}",
            ),
        )
        jobs_repo.create_job(
            session,
            job_type=JobType.SYNC_ARTICLES,
            target_type="account",
            target_id=account.id,
            provider="mock",
        )
    session.commit()

    settings = dataclasses.replace(get_settings(), metrics_concurrency=4)
    tracker = _ArticlesTracker()
    processed = asyncio.run(
        engine.run_pending(session, max_jobs=50, provider=tracker, settings=settings)
    )

    assert processed >= 10
    # Article syncs for different accounts run in parallel, bounded by the cap.
    assert tracker.max_inflight >= 2
    assert tracker.max_inflight <= 4
