"""Provider registry: resolve a provider adapter by name or as a failover chain.

Business code calls :func:`get_provider` and only sees the ``WeChatProvider``
interface, so swapping vendors never touches services or routes.

- ``get_provider("qovia")`` / ``get_provider(account.primary_provider)`` → that
  single adapter (used for id-scoped collection).
- ``get_provider()`` → an ordered **failover chain** built from
  ``PROVIDER_ORDER`` (or ``DEFAULT_PROVIDER`` when unset). When one source
  raises, keyword searches automatically switch to the next.
"""

from __future__ import annotations

from collections.abc import Callable

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.providers.base import WeChatProvider

_FACTORIES: dict[str, Callable[[Settings], WeChatProvider]] = {}
_INSTANCES: dict[str, WeChatProvider] = {}
_CHAIN: WeChatProvider | None = None


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
            api_key=settings.xmedi_api_key,
            base_url=settings.xmedi_base_url,
            timeout=settings.provider_timeout_seconds,
            max_retries=settings.provider_max_retries,
        ),
    )


def available_providers() -> list[str]:
    _ensure_defaults()
    return sorted(_FACTORIES)


def configured_providers(settings: Settings | None = None) -> list[str]:
    """Registered providers that have the credentials needed to be called."""
    _ensure_defaults()
    settings = settings or get_settings()
    return [name for name in sorted(_FACTORIES) if _is_configured(name, settings)]


def _resolve_single(name: str, settings: Settings) -> WeChatProvider:
    resolved = name.strip().lower()
    if resolved not in _FACTORIES:
        raise AppError(f"未知的数据源: {resolved}", code="UNKNOWN_PROVIDER")
    if resolved not in _INSTANCES:
        _INSTANCES[resolved] = _FACTORIES[resolved](settings)
    return _INSTANCES[resolved]


def _is_configured(name: str, settings: Settings) -> bool:
    """Whether a provider has the credentials needed to be worth calling."""
    if name == "qovia":
        return bool(settings.qovia_api_key)
    if name == "xmedi":
        return bool(settings.xmedi_api_key)
    return True


def _build_chain(settings: Settings) -> WeChatProvider:
    order = settings.provider_order or (settings.default_provider,)
    names: list[str] = []
    for raw in order:
        name = raw.strip().lower()
        if name not in _FACTORIES or not _is_configured(name, settings):
            continue
        if name not in names:
            names.append(name)
    if not names:
        names = [settings.default_provider.strip().lower()]
    providers = [_resolve_single(name, settings) for name in names]
    if len(providers) == 1:
        return providers[0]
    from app.providers.failover import FailoverProvider

    return FailoverProvider(providers)


def get_provider(name: str | None = None) -> WeChatProvider:
    _ensure_defaults()
    settings = get_settings()
    if name is not None:
        return _resolve_single(name, settings)
    global _CHAIN
    if _CHAIN is None:
        _CHAIN = _build_chain(settings)
    return _CHAIN


def reset_provider_cache() -> None:
    """Test helper: drop cached adapters + the failover chain."""
    global _CHAIN
    _INSTANCES.clear()
    _CHAIN = None


async def aclose_providers() -> None:
    """Close any cached provider resources (best-effort, on app shutdown)."""
    global _CHAIN
    for provider in list(_INSTANCES.values()):
        close = getattr(provider, "aclose", None)
        if close is not None:
            try:
                await close()
            except Exception:  # pragma: no cover - shutdown best-effort
                pass
    _INSTANCES.clear()
    _CHAIN = None
