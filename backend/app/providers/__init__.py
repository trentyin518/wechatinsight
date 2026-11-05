"""Provider adapters package."""

from app.providers.base import (
    ArticlePage,
    ProviderAccount,
    ProviderArticle,
    ProviderMetrics,
    SearchPage,
    WeChatProvider,
)
from app.providers.registry import available_providers, get_provider, register_provider

__all__ = [
    "ArticlePage",
    "ProviderAccount",
    "ProviderArticle",
    "ProviderMetrics",
    "SearchPage",
    "WeChatProvider",
    "get_provider",
    "register_provider",
    "available_providers",
]
