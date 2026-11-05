"""Task: sync an account's article history page-by-page with cursor resume."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import ProviderError
from app.db.models import SyncJob, WechatAccount
from app.providers.base import WeChatProvider
from app.repositories import accounts as accounts_repo
from app.repositories import articles as articles_repo
from app.repositories import jobs as jobs_repo
from app.repositories import usage as usage_repo


async def sync_articles(
    session: Session,
    job: SyncJob,
    account: WechatAccount,
    provider: WeChatProvider,
    *,
    max_pages: int = 5,
    page_size: int = 20,
) -> int:
    """Sync at most ``max_pages`` of articles, persisting the cursor between runs."""
    provider_id = accounts_repo.get_provider_account_id(session, account)
    if not provider_id:
        raise ProviderError("缺少供应商账号映射，无法同步。")

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
    session.flush()
    return total_written
