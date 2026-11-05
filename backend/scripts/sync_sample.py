"""Sample real-data sync: one page of articles + one metric snapshot.

Requires a configured real provider (API key) and a database with schema applied.
With the default mock provider this also serves as a manual end-to-end check.

Usage:
  DATABASE_URL=... DEFAULT_PROVIDER=qovia python -m scripts.sync_sample "科技"
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

from app.db.models import JobType, WechatArticle
from app.db.session import SessionLocal, init_db
from app.providers.registry import get_provider
from app.repositories import accounts as accounts_repo
from app.repositories import jobs as jobs_repo
from worker.tasks import sync_articles, sync_metrics


async def run(keyword: str, provider_name: str | None) -> None:
    init_db()
    db = SessionLocal()
    try:
        provider = get_provider(provider_name)
        result = await provider.search_accounts(keyword, page=1, page_size=1)
        if not result.items:
            print(f"未找到与 {keyword!r} 匹配的账号")
            return

        account = accounts_repo.upsert_from_provider(db, result.items[0])
        db.commit()
        print(f"账号：{account.name} (id={account.id})")

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

        article = (
            db.query(WechatArticle)
            .filter(WechatArticle.account_id == account.id)
            .order_by(WechatArticle.id)
            .first()
        )
        if article is None:
            print("没有可采集指标的文章")
            return

        mjob = jobs_repo.create_job(
            db,
            job_type=JobType.SYNC_METRICS,
            target_type="article",
            target_id=article.id,
            provider=provider.name,
        )
        db.commit()
        from app.db.models import ArticleMetric

        await sync_metrics.sync_metrics(db, mjob, article, provider)
        db.commit()
        written = db.query(ArticleMetric).filter(ArticleMetric.article_id == article.id).count()
        if written:
            print(f"已为文章 {article.id} 写入指标快照")
        else:
            print(f"数据源未返回文章 {article.id} 的互动指标（已标记为缺失，不写入 0）")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("keyword", help="用于搜索样例账号的关键词")
    parser.add_argument("--provider", default=None, help="数据源（默认取 DEFAULT_PROVIDER）")
    args = parser.parse_args()
    asyncio.run(run(args.keyword, args.provider))


if __name__ == "__main__":
    main()
