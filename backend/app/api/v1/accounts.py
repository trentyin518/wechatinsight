"""Account query endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_approved
from app.core.errors import NotFoundError
from app.db.models import ArticleMetric, User, WechatAccount
from app.schemas.accounts import AccountDetail, AccountOut, AccountSearchResponse
from app.schemas.articles import ArticleListItem, ArticleListResponse
from app.services import accounts as accounts_service
from app.services import articles as articles_service

router = APIRouter(tags=["accounts"])


def _account_out(account: WechatAccount) -> AccountOut:
    return AccountOut(
        id=account.id,
        name=account.name,
        wechat_id=account.wechat_id,
        description=account.description,
        avatar_url=account.avatar_url,
        provider=account.primary_provider,
        last_synced_at=account.last_synced_at,
    )


def _account_detail(account: WechatAccount) -> AccountDetail:
    return AccountDetail(
        id=account.id,
        name=account.name,
        wechat_id=account.wechat_id,
        description=account.description,
        avatar_url=account.avatar_url,
        verification_subject=account.verification_subject,
        account_type=account.account_type,
        provider=account.primary_provider,
        created_at=account.created_at,
        updated_at=account.updated_at,
        last_synced_at=account.last_synced_at,
    )


def _article_item(article, metric: ArticleMetric | None) -> ArticleListItem:
    return ArticleListItem(
        id=article.id,
        title=article.title,
        article_url=article.article_url,
        provider=article.provider,
        published_at=article.published_at,
        read_count=metric.read_count if metric else None,
        like_count=metric.like_count if metric else None,
        wow_count=metric.wow_count if metric else None,
        comment_count=metric.comment_count if metric else None,
        share_count=metric.share_count if metric else None,
        metrics_observed_at=metric.observed_at if metric else None,
    )


@router.get("/accounts", response_model=AccountSearchResponse)
async def search_accounts(
    q: str = Query("", description="关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_db),
    _user: User | None = Depends(require_approved),
) -> AccountSearchResponse:
    result = await accounts_service.search_accounts(session, q, page, page_size)
    session.commit()
    return AccountSearchResponse(
        items=[_account_out(a) for a in result.items],
        page=page,
        page_size=page_size,
        total=result.total,
    )


@router.get("/accounts/{account_id}", response_model=AccountDetail)
def get_account(
    account_id: int,
    session: Session = Depends(get_db),
    _user: User | None = Depends(require_approved),
) -> AccountDetail:
    account = accounts_service.get_account(session, account_id)
    if account is None:
        raise NotFoundError("公众号不存在。")
    return _account_detail(account)


@router.get("/accounts/{account_id}/articles", response_model=ArticleListResponse)
def list_account_articles(
    account_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_db),
    _user: User | None = Depends(require_approved),
) -> ArticleListResponse:
    account = accounts_service.get_account(session, account_id)
    if account is None:
        raise NotFoundError("公众号不存在。")
    rows, total = articles_service.list_articles(session, account_id, page, page_size)
    return ArticleListResponse(
        items=[_article_item(article, metric) for article, metric in rows],
        page=page,
        page_size=page_size,
        total=total,
    )
