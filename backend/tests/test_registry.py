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
