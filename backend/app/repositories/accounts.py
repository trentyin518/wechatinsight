"""Account persistence: search, detail and provider-mapping upsert."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    JobStatus,
    JobType,
    ProviderAccountMapping,
    SyncJob,
    WechatAccount,
    WechatArticle,
)
from app.providers.base import ProviderAccount


@dataclass(slots=True)
class AccountFilters:
    """Server-side account filters. ``None`` means "not constrained".

    Numeric bounds exclude accounts whose value is NULL (unknown), which keeps
    "missing" distinct from a real 0.
    """

    category: str | None = None
    region: str | None = None
    fans_min: int | None = None
    fans_max: int | None = None
    read_min: int | None = None
    read_max: int | None = None
    price_min: int | None = None
    price_max: int | None = None
    ad_min: int | None = None
    ad_max: int | None = None
    xigua_min: float | None = None
    recent_days: int | None = None
    is_original: bool | None = None
    has_video: bool | None = None
    service_only: bool | None = None


def get_by_id(session: Session, account_id: int) -> WechatAccount | None:
    return session.get(WechatAccount, account_id)


def ids_with_pending_collection(session: Session, account_ids: list[int]) -> set[int]:
    """Subset of ``account_ids`` with an in-flight demand-driven collection job.

    Counts both the article-sync phase (job targets the account) and the
    metrics phase (job targets one of the account's articles), so the UI can
    show "采集中…" until the enrichment settles.
    """
    if not account_ids:
        return set()
    active = (JobStatus.PENDING, JobStatus.RUNNING, JobStatus.RETRY)

    pending: set[int] = set(
        session.scalars(
            select(SyncJob.target_id).where(
                SyncJob.job_type == JobType.SYNC_ARTICLES,
                SyncJob.target_type == "account",
                SyncJob.target_id.in_(account_ids),
                SyncJob.status.in_(active),
            )
        )
    )
    metrics_accounts: set[int] = set(
        session.scalars(
            select(WechatArticle.account_id)
            .join(SyncJob, SyncJob.target_id == WechatArticle.id)
            .where(
                SyncJob.job_type == JobType.SYNC_METRICS,
                SyncJob.target_type == "article",
                SyncJob.status.in_(active),
                WechatArticle.account_id.in_(account_ids),
            )
        )
    )
    return pending | metrics_accounts


@dataclass(slots=True)
class CollectionState:
    """Coarse enrichment status for the UI, so "—" is never ambiguous.

    One of: ``idle`` (never attempted), ``collecting`` (job queued/running),
    ``failed`` (last attempt errored, e.g. provider billing/auth), ``empty``
    (synced but the source has no public articles) or ``collected`` (has data).
    """

    state: str
    error_code: str | None = None


def collection_states(
    session: Session, accounts: list[WechatAccount]
) -> dict[int, CollectionState]:
    """Enrichment status for each account, computed in a couple of set queries.

    Precedence: in-flight > has-data > last-attempt-failed > synced-but-empty >
    never-attempted. Showing "failed" only when there's no data keeps a stale
    refresh failure from hiding otherwise-usable numbers.
    """
    if not accounts:
        return {}
    ids = [a.id for a in accounts]
    collecting = ids_with_pending_collection(session, ids)

    latest = (
        select(SyncJob.target_id, func.max(SyncJob.id).label("mid"))
        .where(
            SyncJob.job_type == JobType.SYNC_ARTICLES,
            SyncJob.target_type == "account",
            SyncJob.target_id.in_(ids),
        )
        .group_by(SyncJob.target_id)
        .subquery()
    )
    latest_rows = session.execute(
        select(SyncJob.target_id, SyncJob.status, SyncJob.error_code).join(
            latest, SyncJob.id == latest.c.mid
        )
    ).all()
    latest_map: dict[int, tuple[str, str | None]] = {
        target_id: (status, code) for target_id, status, code in latest_rows
    }

    states: dict[int, CollectionState] = {}
    for account in accounts:
        if account.id in collecting:
            states[account.id] = CollectionState("collecting")
            continue
        if account.article_count and account.article_count > 0:
            states[account.id] = CollectionState("collected")
            continue
        status, code = latest_map.get(account.id, ("", None))
        if status == JobStatus.FAILED:
            states[account.id] = CollectionState("failed", code)
        elif account.last_synced_at is not None:
            states[account.id] = CollectionState("empty")
        else:
            states[account.id] = CollectionState("idle")
    return states


def similar_accounts(
    session: Session, target: WechatAccount, limit: int = 8
) -> list[WechatAccount]:
    """Rank other accounts by similarity to ``target``.

    Signals: same 行业 (strong), 粉丝量级 closeness (ratio), same 地区 (mild).
    Accounts that share neither the industry nor a comparable fan scale are
    dropped so recommendations stay relevant.
    """
    candidates = list(
        session.scalars(select(WechatAccount).where(WechatAccount.id != target.id))
    )

    def fans_ratio(a: int | None, b: int | None) -> float | None:
        if not a or not b:
            return None
        lo, hi = (a, b) if a <= b else (b, a)
        return lo / hi if hi else None

    scored: list[tuple[float, WechatAccount]] = []
    for candidate in candidates:
        same_category = bool(
            target.category and candidate.category and candidate.category == target.category
        )
        score = 0.0
        if same_category:
            score += 100.0
        elif target.category and candidate.category:
            score -= 40.0
        ratio = fans_ratio(target.estimated_fans, candidate.estimated_fans)
        if ratio is not None:
            score += 60.0 * ratio
        if target.region and candidate.region and candidate.region == target.region:
            score += 8.0

        relevant = same_category or (ratio is not None and ratio >= 0.2)
        if not relevant and (target.category or target.estimated_fans):
            continue
        scored.append((score, candidate))

    scored.sort(key=lambda item: (item[0], item[1].id), reverse=True)
    return [candidate for _score, candidate in scored[:limit]]


def _filter_conditions(filters: AccountFilters | None):
    conditions = []
    if filters is None:
        return conditions
    if filters.category:
        conditions.append(WechatAccount.category == filters.category)
    if filters.region:
        conditions.append(WechatAccount.region == filters.region)
    if filters.fans_min is not None:
        conditions.append(WechatAccount.estimated_fans >= filters.fans_min)
    if filters.fans_max is not None:
        conditions.append(WechatAccount.estimated_fans <= filters.fans_max)
    if filters.read_min is not None:
        conditions.append(WechatAccount.avg_read >= filters.read_min)
    if filters.read_max is not None:
        conditions.append(WechatAccount.avg_read <= filters.read_max)
    if filters.price_min is not None:
        conditions.append(WechatAccount.estimated_price >= filters.price_min)
    if filters.price_max is not None:
        conditions.append(WechatAccount.estimated_price <= filters.price_max)
    if filters.ad_min is not None:
        conditions.append(WechatAccount.ad_count_30d >= filters.ad_min)
    if filters.ad_max is not None:
        conditions.append(WechatAccount.ad_count_30d <= filters.ad_max)
    if filters.xigua_min is not None:
        conditions.append(WechatAccount.xigua_index >= filters.xigua_min)
    if filters.recent_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=filters.recent_days)
        conditions.append(WechatAccount.last_synced_at >= cutoff)
    if filters.is_original is not None:
        conditions.append(WechatAccount.is_original.is_(filters.is_original))
    if filters.has_video is not None:
        conditions.append(WechatAccount.has_video.is_(filters.has_video))
    if filters.service_only:
        conditions.append(WechatAccount.account_type == "service")
    return conditions


def search_local(
    session: Session,
    keyword: str,
    page: int,
    page_size: int,
    filters: AccountFilters | None = None,
) -> tuple[list[WechatAccount], int]:
    conditions = []
    kw = (keyword or "").strip()
    if kw:
        pattern = f"%{kw}%"
        conditions.append(
            or_(
                WechatAccount.name.ilike(pattern),
                WechatAccount.wechat_id.ilike(pattern),
                WechatAccount.description.ilike(pattern),
            )
        )
    conditions.extend(_filter_conditions(filters))

    stmt = select(WechatAccount)
    count_stmt = select(func.count(WechatAccount.id))
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    total = session.scalar(count_stmt) or 0
    stmt = stmt.order_by(WechatAccount.id.desc()).offset((page - 1) * page_size).limit(page_size)
    return list(session.scalars(stmt)), total


def search_by_article_local(
    session: Session,
    keyword: str,
    page: int,
    page_size: int,
    filters: AccountFilters | None = None,
) -> tuple[list[WechatAccount], int]:
    """Accounts that have at least one article matching the keyword.

    Matches on article title/summary; results are distinct accounts, paginated
    by account id. Purely local — article search never triggers a paid cold start.
    """
    conditions = []
    kw = (keyword or "").strip()
    if kw:
        pattern = f"%{kw}%"
        conditions.append(
            or_(
                WechatArticle.title.ilike(pattern),
                WechatArticle.summary.ilike(pattern),
            )
        )
    conditions.extend(_filter_conditions(filters))

    join = WechatArticle.account_id == WechatAccount.id
    id_stmt = select(WechatAccount.id).join(WechatArticle, join)
    count_stmt = select(func.count(distinct(WechatAccount.id))).join(WechatArticle, join)
    if conditions:
        id_stmt = id_stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    total = session.scalar(count_stmt) or 0
    id_stmt = id_stmt.distinct().order_by(WechatAccount.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ids = list(session.scalars(id_stmt))
    if not ids:
        return [], total

    found = {a.id: a for a in session.scalars(select(WechatAccount).where(WechatAccount.id.in_(ids)))}
    return [found[i] for i in ids if i in found], total


def find_by_provider_id(
    session: Session, provider: str, provider_account_id: str
) -> WechatAccount | None:
    mapping = session.scalar(
        select(ProviderAccountMapping).where(
            ProviderAccountMapping.provider == provider,
            ProviderAccountMapping.provider_account_id == provider_account_id,
        )
    )
    return mapping.account if mapping else None


def _is_real_provider_id(provider_account_id: str) -> bool:
    """True for a provider-native id (not a synthetic ``content:<name>`` stub)."""
    return bool(provider_account_id) and not provider_account_id.startswith("content:")


def _apply_provider_fields(account: WechatAccount, data: ProviderAccount) -> None:
    """Refresh only fields we actually received; never blank out known data."""
    for attr in (
        "name",
        "wechat_id",
        "avatar_url",
        "description",
        "verification_subject",
        "account_type",
        "category",
        "region",
        "estimated_fans",
        "avg_read",
        "avg_like",
        "avg_wow",
        "avg_share",
        "avg_comment",
        "article_count",
        "estimated_price",
        "ad_count_30d",
        "xigua_index",
        "is_original",
        "has_video",
    ):
        value = getattr(data, attr)
        if value is not None:
            setattr(account, attr, value)


def upsert_from_provider(
    session: Session, data: ProviderAccount, *, priority: str | None = None
) -> WechatAccount:
    """Idempotently create/refresh an account keyed by (provider, provider_id)."""
    account = find_by_provider_id(session, data.provider, data.provider_account_id)

    # Promote a same-named content-derived stub ("content:<name>") to the real
    # account instead of creating a duplicate row for the same official account.
    # The stub's mapping is kept and the real id is added, so both lookups (and
    # the content-derived path) resolve to this single account.
    if account is None and _is_real_provider_id(data.provider_account_id):
        stub = find_by_provider_id(session, data.provider, f"content:{data.name}")
        if stub is not None:
            account = stub
            session.add(
                ProviderAccountMapping(
                    account_id=account.id,
                    provider=data.provider,
                    provider_account_id=data.provider_account_id,
                )
            )

    if account is None:
        account = WechatAccount(
            name=data.name,
            wechat_id=data.wechat_id,
            avatar_url=data.avatar_url,
            description=data.description,
            verification_subject=data.verification_subject,
            account_type=data.account_type,
            category=data.category,
            region=data.region,
            estimated_fans=data.estimated_fans,
            avg_read=data.avg_read,
            avg_like=data.avg_like,
            avg_wow=data.avg_wow,
            avg_share=data.avg_share,
            avg_comment=data.avg_comment,
            article_count=data.article_count,
            estimated_price=data.estimated_price,
            ad_count_30d=data.ad_count_30d,
            xigua_index=data.xigua_index,
            is_original=data.is_original,
            has_video=data.has_video,
            primary_provider=data.provider,
        )
        if priority is not None:
            account.priority = priority
        session.add(account)
        session.flush()
        session.add(
            ProviderAccountMapping(
                account_id=account.id,
                provider=data.provider,
                provider_account_id=data.provider_account_id,
            )
        )
    else:
        _apply_provider_fields(account, data)
    session.flush()
    return account


def get_provider_account_id(session: Session, account: WechatAccount) -> str | None:
    mapping = session.scalar(
        select(ProviderAccountMapping).where(
            ProviderAccountMapping.account_id == account.id,
            ProviderAccountMapping.provider == account.primary_provider,
        )
    )
    return mapping.provider_account_id if mapping else None


def touch_synced(session: Session, account: WechatAccount, when: datetime | None = None) -> None:
    account.last_synced_at = when or datetime.now(timezone.utc)
    session.flush()


def _rounded_mean(values: list[int | None]) -> int | None:
    """Average of the present values, rounded to the nearest int; ``None`` if empty.

    Missing metrics are skipped rather than treated as 0, preserving the
    "unknown stays unknown" invariant used everywhere else.
    """
    present = [v for v in values if v is not None]
    if not present:
        return None
    return int(round(sum(present) / len(present)))


def refresh_derived_attributes(session: Session, account: WechatAccount) -> None:
    """Recompute account aggregates from its collected articles + latest metrics.

    Qovia (and similar providers) expose only account profile facts plus
    per-article interactions — they never return account-level averages. This
    derives 发文篇数 / 平均阅读·点赞·在看·转发·留言, plus 行业-adjacent signals
    (是否原创 via the article majority, 运营地区 via the most common IP region)
    from real rows so the console can rank and filter on real numbers.
    """
    from app.repositories import articles as articles_repo

    articles = list(
        session.scalars(
            select(WechatArticle).where(WechatArticle.account_id == account.id)
        )
    )
    if not articles:
        return

    account.article_count = len(articles)

    latest = articles_repo.latest_metric_map(session, [a.id for a in articles])
    reads = [m.read_count for m in latest.values()]
    likes = [m.like_count for m in latest.values()]
    wows = [m.wow_count for m in latest.values()]
    shares = [m.share_count for m in latest.values()]
    comments = [m.comment_count for m in latest.values()]

    for attr, values in (
        ("avg_read", reads),
        ("avg_like", likes),
        ("avg_wow", wows),
        ("avg_share", shares),
        ("avg_comment", comments),
    ):
        mean = _rounded_mean(values)
        if mean is not None:
            setattr(account, attr, mean)

    original_flags = [a.is_original for a in articles if a.is_original is not None]
    if original_flags:
        # Count as an 原创号 when a majority of collected articles are original.
        account.is_original = sum(bool(f) for f in original_flags) * 2 >= len(original_flags)

    region_counts: dict[str, int] = {}
    for article in articles:
        region = (article.ip_region or "").strip()
        if region:
            region_counts[region] = region_counts.get(region, 0) + 1
    if region_counts:
        account.region = max(region_counts.items(), key=lambda kv: kv[1])[0]

    session.flush()


# Search keywords are frequently topical ("AI 创业", "母婴好物"); map them onto
# the platform's coarse 行业 taxonomy so browsed matches land in the right bucket.
_CATEGORY_HINTS: dict[str, str] = {
    "科技": "科技",
    "互联网": "科技",
    "数码": "科技",
    "手机": "科技",
    "芯片": "科技",
    "人工智能": "科技",
    "ai": "科技",
    "编程": "科技",
    "软件": "科技",
    "财经": "财经",
    "金融": "财经",
    "股票": "财经",
    "投资": "财经",
    "商业": "财经",
    "经济": "财经",
    "理财": "财经",
    "基金": "财经",
    "教育": "教育",
    "学习": "教育",
    "考试": "教育",
    "校园": "教育",
    "留学": "教育",
    "健康": "健康",
    "医疗": "健康",
    "养生": "健康",
    "医学": "健康",
    "健身": "健康",
    "生活": "生活",
    "家居": "生活",
    "母婴": "生活",
    "宠物": "生活",
    "消费": "生活",
    "时尚": "时尚",
    "美妆": "美妆护肤",
    "护肤": "美妆护肤",
    "美食": "美食",
    "美食探店": "美食",
    "旅行": "旅游",
    "旅游": "旅游",
    "汽车": "汽车",
    "娱乐": "娱乐",
    "明星": "娱乐",
    "八卦": "娱乐",
    "体育": "体育",
    "游戏": "游戏动漫",
    "动漫": "游戏动漫",
}


def apply_category_hint(session: Session, account: WechatAccount, keyword: str) -> None:
    """Set ``account.category`` from a search keyword when it is still unknown.

    Never overwrites an existing category, so a provider value (or a prior,
    more specific hint) always wins. ``None`` when nothing matches.
    """
    if account.category:
        return
    lowered = (keyword or "").strip().lower()
    if not lowered:
        return
    # Longer tokens first so specific hints beat generic substrings.
    for token in sorted(_CATEGORY_HINTS, key=len, reverse=True):
        if token in lowered:
            account.category = _CATEGORY_HINTS[token]
            session.flush()
            return
