"""Seed / enrich the console with real provider data (bounded, idempotent).

Phases (each logs usage and refreshes account aggregates via the worker tasks):

  discover  one billed search per category keyword, then pull the first page of
            articles for each match so the account gains real profile + history.
  resync    re-fetch one article page for already-categorized accounts, which
            backfills ``ip_region`` and catches newer posts.
  metrics   fetch interaction metrics for articles that still lack a snapshot,
            capped by ``--metrics-total`` so a run can never overspend.

Re-running is safe: accounts are upserted by ``mp_id``, articles by normalized
URL, and articles that already have a metric snapshot are skipped.

Usage (from backend/):
  DEFAULT_PROVIDER=qovia python -m scripts.seed_real \
    --categories 科技,财经,教育,健康,生活方式 --per-category 3 --metrics-total 40
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import ArticleMetric, JobType, WechatAccount, WechatArticle
from app.db.session import SessionLocal, init_db
from app.providers.base import WeChatProvider
from app.providers.registry import get_provider
from app.repositories import accounts as accounts_repo
from app.repositories import jobs as jobs_repo
from app.repositories import usage as usage_repo
from worker.tasks import sync_articles, sync_metrics

# How many metric calls a single run may spend by default (~$0.005 each).
DEFAULT_METRICS_TOTAL = 40


def _call_cost() -> float:
    return usage_repo.DEFAULT_UNIT_COST_USD


async def _sync_account_articles(
    db: Session, provider: WeChatProvider, account: WechatAccount, pages: int
) -> int:
    job = jobs_repo.create_job(
        db,
        job_type=JobType.SYNC_ARTICLES,
        target_type="account",
        target_id=account.id,
        provider=provider.name,
    )
    db.commit()
    try:
        written = await sync_articles.sync_articles(
            db, job, account, provider, max_pages=pages, page_size=10
        )
        db.commit()
        return written
    except AppError as exc:
        db.rollback()
        print(f"    ! 文章同步失败 [{exc.code}] {exc.message}")
        return 0


async def _discover(
    db: Session,
    provider: WeChatProvider,
    keywords: list[str],
    per_category: int,
    article_pages: int,
) -> int:
    """Search each category and sync the first article page for each match."""
    calls = len(keywords)
    for keyword in keywords:
        try:
            page = await provider.search_accounts(keyword, page=1, page_size=per_category)
        except AppError as exc:
            print(f"  ! 搜索 {keyword!r} 失败 [{exc.code}] {exc.message}")
            continue
        print(f"- {keyword}: {len(page.items)} 个账号")
        # Qovia ignores page_size and returns the full result set; cap to the
        # requested sample so one category cannot balloon the run (time + cost).
        for item in page.items[: per_category]:
            account = accounts_repo.upsert_from_provider(db, item)
            accounts_repo.apply_category_hint(db, account, keyword)
            db.commit()
            written = await _sync_account_articles(db, provider, account, article_pages)
            calls += article_pages
            print(
                f"    · {account.name} (cat={account.category!r}) 新写入文章 {written}"
            )
    return calls


async def _resync_categorized(
    db: Session, provider: WeChatProvider, pages: int
) -> int:
    """Refresh one article page for already-categorized accounts (fills ip_region)."""
    accounts = list(
        db.scalars(
            select(WechatAccount).where(
                WechatAccount.category.is_not(None),
                WechatAccount.primary_provider == provider.name,
            )
        )
    )
    calls = 0
    for account in accounts:
        written = await _sync_account_articles(db, provider, account, pages)
        calls += pages
        print(f"    · 重同步 {account.name} 文章 {written}")
    return calls


async def _fill_metrics(
    db: Session, provider: WeChatProvider, metrics_total: int, per_account: int
) -> int:
    """Fetch metrics for articles lacking a snapshot, newest first, within budget.

    ``per_account`` stops a single high-volume account from consuming the whole
    budget, so coverage is spread across categories.
    """
    accounts = list(
        db.scalars(
            select(WechatAccount).order_by(
                WechatAccount.category.is_(None),  # categorized first
                WechatAccount.article_count.desc().nullslast(),
            )
        )
    )
    used = 0
    for account in accounts:
        if used >= metrics_total:
            break
        used_here = 0
        articles = list(
            db.scalars(
                select(WechatArticle)
                .where(WechatArticle.account_id == account.id)
                .order_by(
                    WechatArticle.published_at.desc().nullslast(),
                    WechatArticle.id.desc(),
                )
            )
        )
        for article in articles:
            if used >= metrics_total or used_here >= per_account:
                break
            has_metric = db.scalar(
                select(func.count(ArticleMetric.id)).where(
                    ArticleMetric.article_id == article.id
                )
            )
            if has_metric:
                continue
            mjob = jobs_repo.create_job(
                db,
                job_type=JobType.SYNC_METRICS,
                target_type="article",
                target_id=article.id,
                provider=provider.name,
            )
            db.commit()
            try:
                await sync_metrics.sync_metrics(db, mjob, article, provider)
                db.commit()
            except AppError as exc:
                db.rollback()
                print(f"    ! 指标失败 article={article.id} [{exc.code}]")
                continue
            used += 1
            used_here += 1
        accounts_repo.refresh_derived_attributes(db, account)
        db.commit()
        if used_here:
            print(f"    · {account.name}: 新增指标 {used_here} 篇")
    return used


def _normalize_categories(db: Session) -> None:
    """Map legacy category values onto the frontend taxonomy so filters match."""
    legacy = {"生活方式": "生活"}
    changed = 0
    for acc in db.scalars(select(WechatAccount).where(WechatAccount.category.in_(legacy))):
        acc.category = legacy[acc.category]  # type: ignore[index]
        changed += 1
    if changed:
        db.commit()
        print(f"规整分类标签 {changed} 个（生活方式 → 生活）")


def _summary(db: Session, provider_name: str) -> None:
    accounts = db.scalar(
        select(func.count()).select_from(WechatAccount).where(
            WechatAccount.primary_provider == provider_name
        )
    )
    articles = db.scalar(
        select(func.count()).select_from(WechatArticle).where(
            WechatArticle.provider == provider_name
        )
    )
    metrics = db.scalar(select(func.count()).select_from(ArticleMetric))
    print(
        f"\n现有 {provider_name} 账号 {accounts} 个，文章 {articles} 篇，指标快照 {metrics} 条。"
    )
    top = db.scalars(
        select(WechatAccount)
        .where(WechatAccount.avg_read.is_not(None))
        .order_by(WechatAccount.avg_read.desc())
        .limit(10)
    )
    print("按平均阅读排序（真实聚合）：")
    for acc in top:
        print(
            f"  {acc.name} | 类目={acc.category} 文章={acc.article_count} "
            f"阅读={acc.avg_read} 点赞={acc.avg_like} 在看={acc.avg_wow} "
            f"地区={acc.region} 原创={acc.is_original}"
        )


async def run(args: argparse.Namespace) -> None:
    init_db()
    db = SessionLocal()
    try:
        provider = get_provider(args.provider)
        if provider.name == "mock" and not args.allow_mock:
            print("当前为 mock 数据源；真实播种请配置 DEFAULT_PROVIDER=qovia 与密钥。")
            print("如确需演练，加 --allow-mock。")
            return

        calls = 0
        if not args.skip_discover:
            keywords = [k.strip() for k in args.categories.split(",") if k.strip()]
            print(f"== 发现阶段：{', '.join(keywords)} ==")
            calls += await _discover(
                db, provider, keywords, args.per_category, args.article_pages
            )
        if args.resync_articles:
            print("== 重同步阶段：为已分类账号刷新文章/地区 ==")
            calls += await _resync_categorized(db, provider, args.article_pages)
        if not args.skip_metrics:
            print(f"== 指标阶段：上限 {args.metrics_total} 次，单账号 {args.metrics_per_account} 篇 ==")
            used = await _fill_metrics(
                db, provider, args.metrics_total, args.metrics_per_account
            )
            calls += used
            print(f"   本轮采集指标 {used} 篇")

        print(f"\n本轮 API 调用约 {calls} 次，预估成本 ~${calls * _call_cost():.2f}")
        _normalize_categories(db)
        _summary(db, provider.name)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed/enrich real provider data")
    parser.add_argument(
        "--categories",
        default="科技,财经,教育,健康,生活,美食,汽车,娱乐",
        help="逗号分隔的分类关键词",
    )
    parser.add_argument("--per-category", type=int, default=3, help="每个关键词取样账号数")
    parser.add_argument("--article-pages", type=int, default=1, help="每个账号拉取文章页数")
    parser.add_argument(
        "--metrics-total", type=int, default=DEFAULT_METRICS_TOTAL, help="最多采集多少篇指标"
    )
    parser.add_argument(
        "--metrics-per-account", type=int, default=8, help="单个账号最多采集多少篇指标"
    )
    parser.add_argument("--provider", default=None, help="数据源（默认取 DEFAULT_PROVIDER）")
    parser.add_argument("--skip-discover", action="store_true", help="跳过账号发现阶段")
    parser.add_argument("--skip-metrics", action="store_true", help="跳过指标采集阶段")
    parser.add_argument(
        "--resync-articles", action="store_true", help="为已分类账号重拉文章（补 ip_region）"
    )
    parser.add_argument("--allow-mock", action="store_true", help="允许在 mock 源上演练")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
