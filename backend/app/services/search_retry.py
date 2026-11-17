"""Durable retry of cold-start searches that hit an upstream busy.

Shared by the dedicated worker cycle and the API's in-process loop, so retries
make progress whether or not the standalone worker is running.

Each due keyword is retried against the provider. On success the accounts are
ingested and the keyword cache is refreshed, so the user's next search is served
from the local store. On continued "busy" we back off; after the attempt budget
is spent the entry is exhausted.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError, DataSourceBusy
from app.providers.base import WeChatProvider
from app.repositories import accounts as accounts_repo
from app.repositories import search_cache as search_cache_repo
from app.repositories import search_retry_queue as retry_repo
from app.repositories import usage as usage_repo

logger = logging.getLogger("wechat_insight.search_retry")


async def run_search_retries(
    session: Session,
    provider: WeChatProvider,
    settings: Settings | None = None,
    *,
    limit: int = 20,
    now: datetime | None = None,
) -> dict[str, int]:
    settings = settings or get_settings()
    now = now or datetime.now(timezone.utc)
    provider_name = getattr(provider, "name", settings.default_provider)
    if usage_repo.budget_exceeded(
        session,
        daily_budget=settings.daily_budget_usd,
        monthly_budget=settings.monthly_budget_usd,
    ):
        # Never spend on retries once the budget is gone.
        return {"retried": 0, "retry_succeeded": 0}
    rows = retry_repo.due(session, now, limit=limit)
    processed = succeeded = 0
    for row in rows:
        if not retry_repo.claim(session, row):
            continue  # another processor took it
        processed += 1
        try:
            result = await provider.search_accounts(row.keyword, page=1, page_size=25)
        except DataSourceBusy as exc:
            retry_repo.schedule_next(
                session, row, exc.message, now=now,
                base_seconds=settings.search_retry_base_seconds,
            )
            session.commit()
            logger.info("search retry %s busy (attempt %s)", row.keyword, row.attempts)
            continue
        except AppError as exc:
            retry_repo.mark_exhausted(session, row, exc.message)
            session.commit()
            logger.warning("search retry %s failed -> %s", row.keyword, exc.code)
            continue
        except Exception as exc:  # never crash the loop
            logger.exception("search retry %s crashed", row.keyword)
            retry_repo.schedule_next(
                session, row, str(exc), now=now,
                base_seconds=settings.search_retry_base_seconds,
            )
            session.commit()
            continue

        stored_ids: list[int] = []
        for account in result.items:
            persisted = accounts_repo.upsert_from_provider(session, account)
            stored_ids.append(persisted.id)
        search_cache_repo.store(session, provider_name, row.keyword, stored_ids)
        retry_repo.succeed(session, row)
        usage_repo.log_usage(
            session,
            provider=provider_name,
            endpoint="search_retry",
            success=True,
            returned_items=len(result.items),
        )
        session.commit()
        succeeded += 1
        logger.info(
            "search retry %s succeeded (%s accounts cached)", row.keyword, len(result.items)
        )
    return {"retried": processed, "retry_succeeded": succeeded}
