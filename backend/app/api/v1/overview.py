"""Homepage overview endpoint (public, real aggregates only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import WechatAccount
from app.repositories import accounts as accounts_repo
from app.repositories import overview as overview_repo
from app.schemas.accounts import AccountOut
from app.schemas.overview import OverviewResponse

router = APIRouter(tags=["overview"])


def _account_out(account: WechatAccount, state: accounts_repo.CollectionState | None) -> AccountOut:
    return AccountOut(
        id=account.id,
        name=account.name,
        wechat_id=account.wechat_id,
        description=account.description,
        avatar_url=account.avatar_url,
        provider=account.primary_provider,
        last_synced_at=account.last_synced_at,
        article_count=account.article_count,
        collecting=bool(state and state.state == "collecting"),
        collection_state=state.state if state else None,
        collection_error=state.error_code if state else None,
    )


@router.get("/overview", response_model=OverviewResponse)
def get_overview(session: Session = Depends(get_db)) -> OverviewResponse:
    accounts, articles, metrics, providers, last_updated = overview_repo.counts(session)
    recents = overview_repo.recent_accounts(session)
    states = accounts_repo.collection_states(session, recents)
    return OverviewResponse(
        accounts_count=accounts,
        articles_count=articles,
        metrics_count=metrics,
        providers_count=providers,
        last_updated_at=last_updated,
        recent_accounts=[_account_out(a, states.get(a.id)) for a in recents],
    )
