"""Deterministic in-memory provider used for local dev and tests.

It exercises the full loop (search -> articles -> metrics) without any network
or API key. Metrics change slightly on repeated queries so snapshots/series can
be demonstrated. This is clearly a development fixture, not real data.
"""

from __future__ import annotations

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
    ),
    ProviderAccount(
        provider="mock",
        provider_account_id="mock-1002",
        name="示例财经笔记",
        wechat_id="mock_finance",
        description="财经与商业分析（示例数据）",
        avatar_url=None,
    ),
    ProviderAccount(
        provider="mock",
        provider_account_id="mock-1003",
        name="示例生活方式",
        wechat_id="mock_life",
        description="生活方式与消费观察（示例数据）",
        avatar_url=None,
    ),
]


def _articles_for(account_id: str) -> list[ProviderArticle]:
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
