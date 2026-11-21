"""Provider registry: resolve a provider adapter by name.

Business code calls :func:`get_provider` and only sees the ``WeChatProvider``
interface, so swapping vendors never touches services or routes.
"""

from __future__ import annotations

from collections.abc import Callable

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.providers.base import WeChatProvider

_FACTORIES: dict[str, Callable[[Settings], WeChatProvider]] = {}
_INSTANCES: dict[str, WeChatProvider] = {}


def register_provider(name: str, factory: Callable[[Settings], WeChatProvider]) -> None:
    _FACTORIES[name] = factory


def _ensure_defaults() -> None:
    if _FACTORIES:
        return

    from app.providers.mock import MockProvider
    from app.providers.qovia import QoviaProvider
    from app.providers.xmedi import XmediProvider

    register_provider("mock", lambda _settings: MockProvider())
    register_provider(
        "qovia",
        lambda settings: QoviaProvider(
            api_key=settings.qovia_api_key,
            base_url=settings.qovia_base_url,
            timeout=settings.provider_timeout_seconds,
            max_retries=settings.provider_max_retries,
        ),
    )
    register_provider(
        "xmedi",
        lambda settings: XmediProvider(
            api_key=settings.xmedi_api_key, base_url=settings.xmedi_base_url
        ),
    )


def available_providers() -> list[str]:
    _ensure_defaults()
    return sorted(_FACTORIES)


def get_provider(name: str | None = None) -> WeChatProvider:
    _ensure_defaults()
    settings = get_settings()
    resolved = (name or settings.default_provider).strip().lower()
    if resolved not in _FACTORIES:
        raise AppError(
            f"未知的数据源: {resolved}",
            code="UNKNOWN_PROVIDER",
        )
    if resolved not in _INSTANCES:
        _INSTANCES[resolved] = _FACTORIES[resolved](settings)
    return _INSTANCES[resolved]


def reset_provider_cache() -> None:
    """Test helper: drop cached adapter instances."""
    _INSTANCES.clear()


async def aclose_providers() -> None:
    """Close any cached provider resources (best-effort, on app shutdown)."""
    for provider in list(_INSTANCES.values()):
        close = getattr(provider, "aclose", None)
        if close is not None:
            try:
                await close()
            except Exception:  # pragma: no cover - shutdown best-effort
                pass
    _INSTANCES.clear()
