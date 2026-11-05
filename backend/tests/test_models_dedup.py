"""Model-level dedup, mapping and unique-constraint behavior."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import ProviderAccountMapping, WechatAccount, WechatArticle
from app.providers.base import ProviderAccount, ProviderArticle
from app.repositories import accounts as accounts_repo
from app.repositories import articles as articles_repo


def _account(**kw) -> ProviderAccount:
    base = dict(
        provider="mock",
        provider_account_id="mock-1001",
        name="示例科技观察",
        wechat_id="mock_tech",
    )
    base.update(kw)
    return ProviderAccount(**base)


def test_upsert_account_is_idempotent(session):
    first = accounts_repo.upsert_from_provider(session, _account())
    second = accounts_repo.upsert_from_provider(session, _account(name="示例科技观察（更新）"))
    session.commit()

    assert first.id == second.id
    assert session.query(WechatAccount).count() == 1
    assert session.query(ProviderAccountMapping).count() == 1
    assert second.name == "示例科技观察（更新）"


def test_provider_change_keeps_internal_id(session):
    account = accounts_repo.upsert_from_provider(session, _account())
    session.commit()
    original_id = account.id

    # Same provider id, different provider -> new mapping, same account if re-used.
    same = accounts_repo.upsert_from_provider(
        session, _account(provider="mock", provider_account_id="mock-1001")
    )
    session.commit()
    assert same.id == original_id


def test_article_url_normalization_dedup(session):
    account = accounts_repo.upsert_from_provider(session, _account())
    session.flush()

    a1 = articles_repo.upsert_from_provider(
        session,
        account.id,
        ProviderArticle(
            provider="mock",
            title="文章",
            url="https://example.com/p/1?utm_source=x&from=timeline#frag",
        ),
    )
    a2 = articles_repo.upsert_from_provider(
        session,
        account.id,
        ProviderArticle(provider="mock", title="文章", url="https://example.com/p/1"),
    )
    session.commit()

    assert a1.id == a2.id
    assert session.query(WechatArticle).count() == 1


def test_duplicate_article_violates_unique_constraint(session):
    account = accounts_repo.upsert_from_provider(session, _account())
    session.commit()

    art = WechatArticle(
        account_id=account.id,
        provider="mock",
        title="t",
        article_url="https://example.com/p/x",
        normalized_url="https://example.com/p/x",
    )
    session.add(art)
    session.commit()

    dup = WechatArticle(
        account_id=account.id,
        provider="mock",
        title="t2",
        article_url="https://example.com/p/x?utm_source=y",
        normalized_url="https://example.com/p/x",
    )
    session.add(dup)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
