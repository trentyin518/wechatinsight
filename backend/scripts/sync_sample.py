"""Sample real-data sync: one page of articles + metric snapshots.

Requires a configured real provider (API key) and a database with schema applied.
With the default mock provider this also serves as a manual end-to-end check.

Usage:
  DATABASE_URL=... DEFAULT_PROVIDER=qovia python -m scripts.sync_sample "科技"
  python -m scripts.sync_sample "财经" --metrics 5
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

from app.db.models import ArticleMetric, JobType, WechatArticle
from app.db.session import SessionLocal, init_db
from app.providers.registry import get_provider
from app.repositories import accounts as accounts_repo
from app.repositories import jobs as jobs_repo
from worker.tasks import sync_articles, sync_metrics


async def run(keyword: str, provider_name: str | None, metrics_limit: int) -> None:
    init_db()
    db = SessionLocal()
    try:
        provider = get_provider(provider_name)
        result = await provider.search_accounts(keyword, page=1, page_size=1)
        if not result.items:
            print(f"未找到与 {keyword!r} 匹配的账号")
            return

        account = accounts_repo.upsert_from_provider(db, result.items[0])
        accounts_repo.apply_category_hint(db, account, keyword)
        db.commit()
        print(f"账号：{account.name} (id={account.id}) category={account.category!r}")

        job = jobs_repo.create_job(
            db,
            job_type=JobType.SYNC_ARTICLES,
            target_type="account",
            target_id=account.id,
            provider=provider.name,
        )
        db.commit()
        count = await sync_articles.sync_articles(
            db, job, account, provider, max_pages=1, page_size=5
        )
        db.commit()
        print(f"已同步文章：{count} 篇")

        articles = (
            db.query(WechatArticle)
            .filter(WechatArticle.account_id == account.id)
            .order_by(WechatArticle.id)
            .all()
        )
        if not articles:
            print("没有可采集指标的文章")
            return

        synced = 0
        for article in articles:
            if synced >= metrics_limit:
                break
            has_metric = (
                db.query(ArticleMetric)
                .filter(ArticleMetric.article_id == article.id)
                .count()
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
            await sync_metrics.sync_metrics(db, mjob, article, provider)
            db.commit()
            synced += 1
            print(f"  指标已写入 article_id={article.id}")

        # Always refresh from whatever metrics exist (including prior runs).
        accounts_repo.refresh_derived_attributes(db, account)
        db.commit()
        print(
            "聚合："
            f"article_count={account.article_count} "
            f"avg_read={account.avg_read} avg_like={account.avg_like} "
            f"avg_wow={account.avg_wow} avg_share={account.avg_share} "
            f"avg_comment={account.avg_comment}"
        )
        if synced == 0:
            print("本轮未新增指标（目标文章均已有快照，或 metrics_limit=0）")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("keyword", help="用于搜索样例账号的关键词")
    parser.add_argument("--provider", default=None, help="数据源（默认取 DEFAULT_PROVIDER）")
    parser.add_argument(
        "--metrics",
        type=int,
        default=5,
        help="为本账号最多新采多少篇尚无指标的文章（默认 5）",
    )
    args = parser.parse_args()
    asyncio.run(run(args.keyword, args.provider, args.metrics))


if __name__ == "__main__":
    main()
