"""Deterministic in-memory provider used for local dev and tests.

It exercises the full loop (search -> articles -> metrics) without any network
or API key. Metrics change slightly on repeated queries so snapshots/series can
be demonstrated. This is clearly a development fixture, not real data.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.providers.base import (
    ArticlePage,
    ProviderAccount,
    ProviderArticle,
    ProviderMetrics,
    SearchPage,
)

_ACCOUNTS: list[ProviderAccount] = [
    ProviderAccount(
        provider="mock",
        provider_account_id="mock-1001",
        name="示例科技观察",
        wechat_id="mock_tech",
        description="科技行业资讯（示例数据）",
        avatar_url=None,
        verification_subject="示例科技",
        account_type="subscription",
        category="科技",
        region="北京",
        estimated_fans=1275860,
        avg_read=93700,
        avg_like=4519,
        avg_wow=1662,
        avg_share=17691,
        avg_comment=16,
        article_count=71,
        estimated_price=68000,
        ad_count_30d=12,
        xigua_index=2339.9,
        is_original=True,
        has_video=True,
    ),
    ProviderAccount(
        provider="mock",
        provider_account_id="mock-1002",
        name="示例财经笔记",
        wechat_id="mock_finance",
        description="财经与商业分析（示例数据）",
        avatar_url=None,
        verification_subject="示例财经",
        account_type="service",
        category="财经",
        region="上海",
        estimated_fans=82000,
        avg_read=8600,
        avg_like=320,
        avg_wow=95,
        avg_share=1180,
        avg_comment=9,
        article_count=48,
        estimated_price=8800,
        ad_count_30d=3,
        xigua_index=1180.2,
        is_original=True,
        has_video=False,
    ),
    ProviderAccount(
        provider="mock",
        provider_account_id="mock-1003",
        name="示例生活方式",
        wechat_id="mock_life",
        description="生活方式与消费观察（示例数据）",
        avatar_url=None,
        verification_subject="示例文化",
        account_type="subscription",
        category="生活",
        region="广州",
        estimated_fans=210000,
        avg_read=15000,
        avg_like=600,
        avg_wow=210,
        avg_share=3000,
        avg_comment=12,
        article_count=55,
        estimated_price=15000,
        ad_count_30d=6,
        xigua_index=1520.6,
        is_original=False,
        has_video=True,
    ),
    ProviderAccount(
        provider="mock",
        provider_account_id="mock-1004",
        name="示例科技前沿",
        wechat_id="mock_tech_frontier",
        description="前沿科技与产业观察（示例数据）",
        avatar_url=None,
        verification_subject="示例科技",
        account_type="subscription",
        category="科技",
        region="深圳",
        estimated_fans=880000,
        avg_read=62000,
        avg_like=3100,
        avg_wow=980,
        avg_share=12000,
        avg_comment=14,
        article_count=64,
        estimated_price=42000,
        ad_count_30d=8,
        xigua_index=2010.5,
        is_original=True,
        has_video=False,
    ),
    ProviderAccount(
        provider="mock",
        provider_account_id="mock-1005",
        name="示例数码评测",
        wechat_id="mock_digital",
        description="数码产品与评测（示例数据）",
        avatar_url=None,
        verification_subject="示例数码",
        account_type="subscription",
        category="科技",
        region="北京",
        estimated_fans=1560000,
        avg_read=120000,
        avg_like=6200,
        avg_wow=2100,
        avg_share=21000,
        avg_comment=20,
        article_count=80,
        estimated_price=88000,
        ad_count_30d=15,
        xigua_index=2380.1,
        is_original=True,
        has_video=True,
    ),
    ProviderAccount(
        provider="mock",
        provider_account_id="mock-1006",
        name="示例财经观察",
        wechat_id="mock_finance_watch",
        description="宏观财经与市场观察（示例数据）",
        avatar_url=None,
        verification_subject="示例财经",
        account_type="subscription",
        category="财经",
        region="上海",
        estimated_fans=96000,
        avg_read=9000,
        avg_like=350,
        avg_wow=110,
        avg_share=1300,
        avg_comment=8,
        article_count=50,
        estimated_price=9900,
        ad_count_30d=4,
        xigua_index=1210.3,
        is_original=False,
        has_video=False,
    ),
]


def _articles_for(account_id: str) -> list[ProviderArticle]:
    now = datetime.now(timezone.utc)
    articles: list[ProviderArticle] = []
    for i in range(1, 6):
        articles.append(
            ProviderArticle(
                provider="mock",
                provider_article_id=f"{account_id}-a{i}",
                title=f"示例文章 {i}（{account_id}）",
                url=f"https://example.com/{account_id}/article-{i}",
                summary=f"这是一篇示例文章 {i} 的摘要。",
                author="示例作者",
                ip_region="北京" if i % 2 == 1 else "上海",
                published_at=now - timedelta(hours=i * 6),
                is_original=(i % 2 == 0),
                is_paid=False,
            )
        )
    return articles


class MockProvider:
    name = "mock"

    def __init__(self) -> None:
        self._metric_calls: dict[str, int] = {}

    async def search_accounts(
        self, keyword: str, page: int = 1, page_size: int = 20
    ) -> SearchPage:
        kw = (keyword or "").strip().lower()
        matches = [
            a
            for a in _ACCOUNTS
            if kw in a.name.lower() or (a.wechat_id and kw in a.wechat_id.lower())
        ]
        start = max(page - 1, 0) * page_size
        return SearchPage(items=matches[start : start + page_size], next_cursor=None)

    async def get_account(self, provider_account_id: str) -> ProviderAccount | None:
        for account in _ACCOUNTS:
            if account.provider_account_id == provider_account_id:
                return account
        return None

    async def get_articles(
        self,
        provider_account_id: str,
        cursor: str | None = None,
        page_size: int = 20,
        *,
        account_name: str | None = None,
    ) -> ArticlePage:
        articles = _articles_for(provider_account_id)
        offset = int(cursor) if cursor else 0
        page_items = articles[offset : offset + page_size]
        next_cursor = None
        if offset + page_size < len(articles):
            next_cursor = str(offset + page_size)
        return ArticlePage(items=page_items, next_cursor=next_cursor)

    async def get_article_metrics(self, article_url: str) -> ProviderMetrics | None:
        calls = self._metric_calls.get(article_url, 0)
        self._metric_calls[article_url] = calls + 1
        base = 1000
        return ProviderMetrics(
            provider="mock",
            read_count=base + calls * 100,
            like_count=20 + calls,
            wow_count=5 + calls,
            comment_count=None,
            share_count=None,
        )
