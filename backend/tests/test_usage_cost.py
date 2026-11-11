"""Cost model: fabricated mock data must never consume the real budget."""

from __future__ import annotations

from app.repositories import usage as usage_repo


def test_mock_calls_are_free(session) -> None:
    log = usage_repo.log_usage(
        session, provider="mock", endpoint="search_accounts", success=True
    )
    assert log.estimated_cost == 0.0


def test_real_provider_calls_are_billed(session) -> None:
    log = usage_repo.log_usage(
        session, provider="qovia", endpoint="search_accounts", success=True
    )
    assert log.estimated_cost == 0.005
