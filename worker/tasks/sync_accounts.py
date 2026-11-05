"""Task: refresh a single account's profile fields."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import ProviderError
from app.db.models import SyncJob, WechatAccount
from app.providers.base import WeChatProvider
from app.repositories import accounts as accounts_repo
from app.repositories import jobs as jobs_repo
from app.repositories import usage as usage_repo


async def sync_account(
    session: Session, job: SyncJob, account: WechatAccount, provider: WeChatProvider
) -> None:
    provider_id = accounts_repo.get_provider_account_id(session, account)
    if not provider_id:
        raise ProviderError("缺少供应商账号映射，无法同步。")

    data = await provider.get_account(provider_id)
    usage_repo.log_usage(
        session,
        provider=provider.name,
        endpoint="get_account",
        success=True,
        returned_items=1 if data else 0,
        job_id=job.id,
    )
    jobs_repo.add_usage(session, job, api_calls=1, estimated_cost=usage_repo.DEFAULT_UNIT_COST_USD)

    if data is not None:
        accounts_repo.upsert_from_provider(session, data)
    accounts_repo.touch_synced(session, account)
    session.flush()
