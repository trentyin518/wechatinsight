"""Provider registry behavior."""

from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.providers.registry import available_providers, get_provider


def test_mock_provider_resolvable():
    provider = get_provider("mock")
    assert provider.name == "mock"
    assert "mock" in available_providers()


def test_unknown_provider_raises():
    with pytest.raises(AppError) as excinfo:
        get_provider("does-not-exist")
    assert excinfo.value.code == "UNKNOWN_PROVIDER"


import dataclasses  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.providers import registry  # noqa: E402
from app.providers.failover import FailoverProvider  # noqa: E402


def test_failover_chain_from_provider_order(monkeypatch):
    registry.reset_provider_cache()
    settings = dataclasses.replace(
        get_settings(),
        provider_order=("qovia", "xmedi"),
        qovia_api_key="k1",
        xmedi_api_key="k2",
    )
    monkeypatch.setattr(registry, "get_settings", lambda: settings)
    try:
        provider = registry.get_provider()
        assert isinstance(provider, FailoverProvider)
        assert provider.name == "qovia"
        assert [p.name for p in provider.providers] == ["qovia", "xmedi"]
    finally:
        registry.reset_provider_cache()


def test_failover_chain_skips_unconfigured_sources(monkeypatch):
    registry.reset_provider_cache()
    settings = dataclasses.replace(
        get_settings(),
        provider_order=("qovia", "xmedi", "mock"),
        qovia_api_key="",  # not configured → skipped
        xmedi_api_key="k2",
    )
    monkeypatch.setattr(registry, "get_settings", lambda: settings)
    try:
        provider = registry.get_provider()
        assert [p.name for p in provider.providers] == ["xmedi", "mock"]
    finally:
        registry.reset_provider_cache()


def test_default_provider_single_when_no_order(monkeypatch):
    registry.reset_provider_cache()
    settings = dataclasses.replace(
        get_settings(), provider_order=(), default_provider="mock"
    )
    monkeypatch.setattr(registry, "get_settings", lambda: settings)
    try:
        provider = registry.get_provider()
        assert provider.name == "mock"
    finally:
        registry.reset_provider_cache()
