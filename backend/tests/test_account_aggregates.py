"""Derived account aggregates from real article/metric rows."""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.models import ArticleMetric, WechatAccount, WechatArticle
from app.repositories import accounts as accounts_repo


def test_refresh_derived_attributes_averages_latest_metrics(session):
    account = WechatAccount(
        name="聚合测试号",
        primary_provider="mock",
        priority="B",
    )
    session.add(account)
    session.flush()

    a1 = WechatArticle(
        account_id=account.id,
        provider="mock",
        title="一",
        article_url="https://example.com/a1",
        normalized_url="https://example.com/a1",
        is_original=True,
        ip_region="广东",
    )
    a2 = WechatArticle(
        account_id=account.id,
        provider="mock",
        title="二",
        article_url="https://example.com/a2",
        normalized_url="https://example.com/a2",
        is_original=True,
        ip_region="广东",
    )
    session.add_all([a1, a2])
    session.flush()

    now = datetime.now(timezone.utc)
    session.add_all(
        [
            ArticleMetric(
                article_id=a1.id,
                provider="mock",
                read_count=100,
                like_count=10,
                wow_count=1,
                comment_count=2,
                share_count=3,
                observed_at=now,
            ),
            ArticleMetric(
                article_id=a2.id,
                provider="mock",
                read_count=300,
                like_count=30,
                wow_count=5,
                comment_count=4,
                share_count=7,
                observed_at=now,
            ),
        ]
    )
    session.flush()

    accounts_repo.refresh_derived_attributes(session, account)

    assert account.article_count == 2
    assert account.avg_read == 200
    assert account.avg_like == 20
    assert account.avg_wow == 3
    assert account.avg_share == 5
    assert account.avg_comment == 3
    assert account.is_original is True
    assert account.region == "广东"


def test_apply_category_hint_only_when_empty(session):
    account = WechatAccount(name="分类提示", primary_provider="mock", priority="B")
    session.add(account)
    session.flush()

    accounts_repo.apply_category_hint(session, account, "科技")
    assert account.category == "科技"

    accounts_repo.apply_category_hint(session, account, "财经")
    assert account.category == "科技"
