"""Task: sync an account's article history page-by-page with cursor resume.

On a demand-driven search this runs with a small page budget (default: the first
page only) so we never walk an account's whole history in one go. After the
articles land it chains a bounded set of metrics jobs so account averages
(头条平均阅读/点赞/在看/转发/留言) can be computed.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ProviderError
from app.db.models import SyncJob, WechatAccount
from app.providers.base import WeChatProvider
from app.repositories import accounts as accounts_repo
from app.repositories import articles as articles_repo
from app.repositories import jobs as jobs_repo
from app.repositories import usage as usage_repo
from app.services import collection as collection_service

logger = logging.getLogger("wechat_insight.worker.sync_articles")


async def sync_articles(
    session: Session,
    job: SyncJob,
    account: WechatAccount,
    provider: WeChatProvider,
    *,
    max_pages: int | None = None,
    page_size: int = 20,
    settings: Settings | None = None,
) -> int:
    """Sync at most ``max_pages`` of articles, persisting the cursor between runs.

    ``max_pages`` defaults to ``settings.article_sync_max_pages`` (1) so an
    on-demand sync only pulls the newest page.
    """
    provider_id = accounts_repo.get_provider_account_id(session, account)
    if not provider_id:
        raise ProviderError("缺少供应商账号映射，无法同步。")

    if max_pages is None:
        max_pages = (settings or get_settings()).article_sync_max_pages

    cursor = job.cursor
    pages = 0
    total_written = 0
    while pages < max_pages:
        page = await provider.get_articles(
            provider_id, cursor=cursor, page_size=page_size, account_name=account.name
        )
        usage_repo.log_usage(
            session,
            provider=provider.name,
            endpoint="get_articles",
            success=True,
            returned_items=len(page.items),
            job_id=job.id,
        )
        jobs_repo.add_usage(
            session, job, api_calls=1, estimated_cost=usage_repo.DEFAULT_UNIT_COST_USD
        )
        for item in page.items:
            articles_repo.upsert_from_provider(session, account.id, item)
            total_written += 1
        cursor = page.next_cursor
        jobs_repo.set_cursor(session, job, cursor)
        pages += 1
        if not cursor:
            break

    accounts_repo.touch_synced(session, account)
    accounts_repo.refresh_derived_attributes(session, account)

    # Chain a bounded set of metrics jobs for the articles we just collected so
    # the 在看/转发/留言 averages can be filled too (a later worker cycle runs
    # them). Best-effort: scheduling failures never fail the article sync.
    try:
        collection_service.enqueue_metrics_for_account(
            session, account, settings=settings or get_settings()
        )
    except Exception:
        logger.exception("failed to enqueue metrics after article sync for %s", account.id)

    session.flush()
    return total_written
