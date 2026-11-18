"""Account query endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_approved
from app.core.errors import NotFoundError
from app.db.models import ArticleMetric, User, WechatAccount
from app.repositories import accounts as accounts_repo
from app.repositories.accounts import AccountFilters
from app.schemas.accounts import (
    AccountDetail,
    AccountOut,
    AccountSearchResponse,
    SimilarAccountsResponse,
)
from app.schemas.articles import ArticleListItem, ArticleListResponse
from app.services import accounts as accounts_service
from app.services import articles as articles_service

router = APIRouter(tags=["accounts"])


def _account_out(account: WechatAccount, *, collecting: bool = False) -> AccountOut:
    return AccountOut(
        id=account.id,
        name=account.name,
        wechat_id=account.wechat_id,
        description=account.description,
        avatar_url=account.avatar_url,
        verification_subject=account.verification_subject,
        account_type=account.account_type,
        provider=account.primary_provider,
        last_synced_at=account.last_synced_at,
        category=account.category,
        region=account.region,
        estimated_fans=account.estimated_fans,
        avg_read=account.avg_read,
        avg_like=account.avg_like,
        avg_wow=account.avg_wow,
        avg_share=account.avg_share,
        avg_comment=account.avg_comment,
        article_count=account.article_count,
        estimated_price=account.estimated_price,
        ad_count_30d=account.ad_count_30d,
        xigua_index=account.xigua_index,
        is_original=account.is_original,
        has_video=account.has_video,
        collecting=collecting,
    )


def _account_detail(account: WechatAccount, *, collecting: bool = False) -> AccountDetail:
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
        category=account.category,
        region=account.region,
        estimated_fans=account.estimated_fans,
        avg_read=account.avg_read,
        avg_like=account.avg_like,
        avg_wow=account.avg_wow,
        avg_share=account.avg_share,
        avg_comment=account.avg_comment,
        article_count=account.article_count,
        estimated_price=account.estimated_price,
        ad_count_30d=account.ad_count_30d,
        xigua_index=account.xigua_index,
        is_original=account.is_original,
        has_video=account.has_video,
        collecting=collecting,
    )


def _article_item(article, metric: ArticleMetric | None) -> ArticleListItem:
    return ArticleListItem(
        id=article.id,
        title=article.title,
        article_url=article.article_url,
        provider=article.provider,
        published_at=article.published_at,
        ip_region=article.ip_region,
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
    mode: str = Query("name", pattern="^(name|article)$", description="检索方式：name=账号，article=文章内容"),
    category: str | None = Query(None, description="所属行业"),
    region: str | None = Query(None, description="所在地区"),
    fans_min: int | None = Query(None, ge=0, description="预估活粉下限"),
    fans_max: int | None = Query(None, ge=0, description="预估活粉上限"),
    read_min: int | None = Query(None, ge=0, description="平均阅读下限"),
    read_max: int | None = Query(None, ge=0, description="平均阅读上限"),
    price_min: int | None = Query(None, ge=0, description="预估报价下限"),
    price_max: int | None = Query(None, ge=0, description="预估报价上限"),
    ad_min: int | None = Query(None, ge=0, description="30天广告数下限"),
    ad_max: int | None = Query(None, ge=0, description="30天广告数上限"),
    xigua_min: float | None = Query(None, ge=0, description="西瓜指数下限"),
    recent_days: int | None = Query(None, ge=1, description="近N天有采集"),
    is_original: bool | None = Query(None, description="仅原创号"),
    has_video: bool | None = Query(None, description="仅带视频内容"),
    service_only: bool | None = Query(None, description="仅服务号"),
    session: Session = Depends(get_db),
    _user: User | None = Depends(require_approved),
) -> AccountSearchResponse:
    filters = AccountFilters(
        category=(category or None),
        region=(region or None),
        fans_min=fans_min,
        fans_max=fans_max,
        read_min=read_min,
        read_max=read_max,
        price_min=price_min,
        price_max=price_max,
        ad_min=ad_min,
        ad_max=ad_max,
        xigua_min=xigua_min,
        recent_days=recent_days,
        is_original=is_original,
        has_video=has_video,
        service_only=service_only,
    )
    result = await accounts_service.search_accounts(
        session, q, page, page_size, filters=filters, mode=mode
    )
    session.commit()
    collecting = accounts_repo.ids_with_pending_collection(
        session, [a.id for a in result.items]
    )
    return AccountSearchResponse(
        items=[_account_out(a, collecting=a.id in collecting) for a in result.items],
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
    collecting = accounts_repo.ids_with_pending_collection(session, [account.id])
    return _account_detail(account, collecting=account.id in collecting)


@router.get("/accounts/{account_id}/similar", response_model=SimilarAccountsResponse)
def get_similar_accounts(
    account_id: int,
    limit: int = Query(8, ge=1, le=20),
    session: Session = Depends(get_db),
    _user: User | None = Depends(require_approved),
) -> SimilarAccountsResponse:
    account = accounts_service.get_account(session, account_id)
    if account is None:
        raise NotFoundError("公众号不存在。")
    items = accounts_repo.similar_accounts(session, account, limit=limit)
    collecting = accounts_repo.ids_with_pending_collection(
        session, [account.id, *(item.id for item in items)]
    )
    return SimilarAccountsResponse(
        account=_account_out(account, collecting=account.id in collecting),
        items=[_account_out(item, collecting=item.id in collecting) for item in items],
    )


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
