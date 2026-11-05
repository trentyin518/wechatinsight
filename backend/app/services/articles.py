"""Article query service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import ArticleMetric, WechatArticle
from app.repositories import articles as articles_repo


def list_articles(
    session: Session, account_id: int, page: int, page_size: int
) -> tuple[list[tuple[WechatArticle, ArticleMetric | None]], int]:
    rows, total = articles_repo.list_by_account(session, account_id, page, page_size)
    latest = articles_repo.latest_metric_map(session, [r.id for r in rows])
    return [(row, latest.get(row.id)) for row in rows], total


def get_article(
    session: Session, article_id: int
) -> tuple[WechatArticle, ArticleMetric | None] | None:
    article = articles_repo.get_by_id(session, article_id)
    if article is None:
        return None
    latest = articles_repo.latest_metric_map(session, [article.id]).get(article.id)
    return article, latest


def metrics_history(
    session: Session, article_id: int
) -> tuple[list[ArticleMetric], tuple[int | None, float | None]]:
    points = articles_repo.list_metrics(session, article_id)
    change = articles_repo.observed_read_change(points)
    return points, change
