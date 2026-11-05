"""Controlled cold-start: rate limit and quota guards."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.core.errors import QuotaExceeded, RateLimited
from app.providers.mock import MockProvider
from app.repositories import usage as usage_repo
from app.services import accounts as accounts_service
from app.services.ratelimit import rate_limiter


def _settings(**overrides):
    base = get_settings()
    data = dict(base.__dict__)
    data.update(overrides)
    return base.__class__(**data)


async def test_quota_exceeded_blocks_cold_start(session):
    usage_repo.log_usage(session, provider="mock", endpoint="x", success=True, estimated_cost=999)
    session.commit()
    settings = _settings(daily_budget_usd=0.01)
    with pytest.raises(QuotaExceeded):
        await accounts_service.search_accounts(session, "示例", 1, 20, settings=settings)


async def test_rate_limit_blocks_repeated_cold_start(session):
    rate_limiter.reset()
    settings = _settings(search_rate_limit_per_minute=1)
    provider = MockProvider()
    # Keyword with no mock matches still exercises the cold-start path.
    await accounts_service.search_accounts(
        session, "no-match-keyword", 1, 20, provider=provider, settings=settings
    )
    with pytest.raises(RateLimited):
        await accounts_service.search_accounts(
            session, "no-match-keyword", 1, 20, provider=provider, settings=settings
        )
