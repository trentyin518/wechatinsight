"""Application settings loaded from environment variables / .env files."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

# Load backend/.env first then repo-root .env (root wins if both set).
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(REPO_ROOT / ".env")

DEFAULT_DATABASE_URL = "sqlite+pysqlite:///./dev.db"


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _float(value: str | None, default: float) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except ValueError:
        return default


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    default_provider: str
    cors_origins: tuple[str, ...]
    daily_budget_usd: float
    monthly_budget_usd: float
    allow_cold_start_search: bool
    search_rate_limit_per_minute: int
    qovia_api_key: str
    qovia_base_url: str
    xmedi_api_key: str
    xmedi_base_url: str
    # Search-result cache: identical keywords are answered from the DB instead of
    # hitting a billed provider again. Empty results are kept longer on purpose.
    search_cache_ttl_hours: int = 24
    empty_search_cache_ttl_hours: int = 168

    # Authentication & onboarding. AUTH_ENFORCED gates whether data endpoints
    # require an approved session; it defaults to False so the endpoints and UI
    # can ship first, then be switched on (and rolled back) without a migration.
    auth_enforced: bool = False
    session_ttl_hours: int = 168
    session_cookie_name: str = "wi_session"
    session_secret: str = "dev-insecure-change-me"
    frontend_base_url: str = "http://localhost:3000"
    # WeChat 网站应用 OAuth2. When app_id/secret are missing, mock login is used
    # (non-production only).
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_redirect_uri: str = "http://localhost:8000/api/v1/auth/wechat/callback"
    wechat_state_ttl_seconds: int = 600
    # Onboarding proof uploads.
    proof_max_mb: int = 5
    upload_dir: str = ""
    # Idempotently bootstrapped admin (used to review onboarding submissions).
    admin_phone: str = ""
    admin_password: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    origins = tuple(o.strip() for o in origins_raw.split(",") if o.strip())
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        database_url=os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL,
        default_provider=os.getenv("DEFAULT_PROVIDER", "mock"),
        cors_origins=origins,
        daily_budget_usd=_float(os.getenv("DAILY_BUDGET_USD"), 5.0),
        monthly_budget_usd=_float(os.getenv("MONTHLY_BUDGET_USD"), 100.0),
        allow_cold_start_search=_bool(os.getenv("ALLOW_COLD_START_SEARCH"), True),
        search_rate_limit_per_minute=_int(os.getenv("SEARCH_RATE_LIMIT_PER_MINUTE"), 30),
        qovia_api_key=os.getenv("QOVIA_API_KEY", ""),
        qovia_base_url=os.getenv("QOVIA_BASE_URL", "https://api.qovia.example.com"),
        xmedi_api_key=os.getenv("XMEDI_API_KEY", ""),
        xmedi_base_url=os.getenv("XMEDI_BASE_URL", "https://api.xmedi.example.com"),
        search_cache_ttl_hours=_int(os.getenv("SEARCH_CACHE_TTL_HOURS"), 24),
        empty_search_cache_ttl_hours=_int(os.getenv("EMPTY_SEARCH_CACHE_TTL_HOURS"), 168),
        auth_enforced=_bool(os.getenv("AUTH_ENFORCED"), False),
        session_ttl_hours=_int(os.getenv("SESSION_TTL_HOURS"), 168),
        session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "wi_session"),
        session_secret=os.getenv("SESSION_SECRET", "dev-insecure-change-me"),
        frontend_base_url=os.getenv("FRONTEND_BASE_URL") or (origins[0] if origins else "http://localhost:3000"),
        wechat_app_id=os.getenv("WECHAT_APP_ID", ""),
        wechat_app_secret=os.getenv("WECHAT_APP_SECRET", ""),
        wechat_redirect_uri=os.getenv(
            "WECHAT_REDIRECT_URI", "http://localhost:8000/api/v1/auth/wechat/callback"
        ),
        wechat_state_ttl_seconds=_int(os.getenv("WECHAT_STATE_TTL_SECONDS"), 600),
        proof_max_mb=_int(os.getenv("PROOF_MAX_MB"), 5),
        upload_dir=os.getenv("UPLOAD_DIR") or str(BACKEND_DIR / "uploads"),
        admin_phone=os.getenv("ADMIN_PHONE", ""),
        admin_password=os.getenv("ADMIN_PASSWORD", ""),
    )
