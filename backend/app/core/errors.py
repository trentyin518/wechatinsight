"""Domain errors mapped to a stable API error envelope.

The API never leaks third-party raw errors, keys or internal details. Every
error carries a stable machine-readable ``code`` and an HTTP status.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for expected, client-visible application errors."""

    status_code: int = 400
    code: str = "BAD_REQUEST"
    default_message: str = "请求无法处理。"

    def __init__(self, message: str | None = None, *, code: str | None = None) -> None:
        self.message = message or self.default_message
        if code is not None:
            self.code = code
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    default_message = "请求的资源不存在。"


class ValidationError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    default_message = "请求参数不合法。"


class DataSourceUnavailable(AppError):
    status_code = 503
    code = "DATA_SOURCE_UNAVAILABLE"
    default_message = "当前暂时无法更新数据，请稍后重试。"


class DataSourceBillingError(AppError):
    status_code = 402
    code = "DATA_SOURCE_BILLING"
    default_message = "数据源余额不足，请充值后重试。"


class DataSourceRateLimited(AppError):
    status_code = 429
    code = "DATA_SOURCE_RATE_LIMITED"
    default_message = "数据源请求过于频繁，请稍后重试。"


class QuotaExceeded(AppError):
    status_code = 429
    code = "QUOTA_EXCEEDED"
    default_message = "查询额度已用尽，请稍后重试。"


class RateLimited(AppError):
    status_code = 429
    code = "RATE_LIMITED"
    default_message = "请求过于频繁，请稍后重试。"


class ProviderError(AppError):
    """Raised by adapters for unexpected provider failures (never leaked raw)."""

    status_code = 502
    code = "DATA_SOURCE_ERROR"
    default_message = "数据源返回异常，请稍后重试。"
