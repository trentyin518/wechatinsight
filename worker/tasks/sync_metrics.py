"""Task: append a metric snapshot for a single article."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import SyncJob, WechatArticle
from app.providers.base import WeChatProvider
from app.repositories import articles as articles_repo
from app.repositories import jobs as jobs_repo
from app.repositories import usage as usage_repo


async def sync_metrics(
    session: Session, job: SyncJob, article: WechatArticle, provider: WeChatProvider
) -> None:
    data = await provider.get_article_metrics(article.article_url)
    usage_repo.log_usage(
        session,
        provider=provider.name,
        endpoint="get_article_metrics",
        success=True,
        returned_items=1 if data else 0,
        job_id=job.id,
    )
    jobs_repo.add_usage(session, job, api_calls=1, estimated_cost=usage_repo.DEFAULT_UNIT_COST_USD)

    if data is not None:
        articles_repo.add_metric_snapshot(session, article.id, data)
    session.flush()
