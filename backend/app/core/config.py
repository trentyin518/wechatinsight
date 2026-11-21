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
    # Background retry of cold-start searches that hit an upstream "busy".
    search_retry_max_attempts: int = 8
    search_retry_base_seconds: int = 60
    # How often the API process drains the search-retry queue (0 disables it).
    search_retry_interval_seconds: int = 30
    # Master switch for any *background* search-retry work (API loop + worker).
    # Off by default so nothing repeatedly calls the paid upstream on its own.
    search_retry_enabled: bool = False
    # Proactive collection (account/article/metrics sweep) is OFF by default.
    # The site is demand-driven: the provider is only called when a user's
    # search misses the local cache. Turn on only when you intentionally want
    # a background refresh window.
    collection_enabled: bool = False
    # Even when collection is on, don't re-fetch an article's metrics within
    # this window (kills the "every 4s per article" cost storm).
    metrics_min_interval_hours: int = 24

    # Demand-driven enrichment: when a user's *search* returns accounts on the
    # visible result page, those accounts (and only those) get a single
    # background SYNC_ARTICLES job. It persists the first page of articles and
    # chains a bounded number of SYNC_METRICS jobs, so the console can show real
    # 发文篇数 / 头条平均* values. Nothing is scheduled on a timer and nothing
    # outside the page the user is viewing is fetched, keeping spend proportional
    # to actual searches. Set ON_DEMAND_SYNC_ENABLED=false to go back to
    # profile-only (no paid enrichment).
    on_demand_sync_enabled: bool = True
    # Don't re-sync an account that was already collected within this window, so
    # repeated identical searches (and pagination round-trips) never pay twice.
    on_demand_sync_ttl_hours: int = 12
    # Only pull the first page of an account's articles on a demand sync — never
    # page through the whole history in one go.
    article_sync_max_pages: int = 1
    # Cap paid per-article metric calls per account per demand sync (0 disables
    # metrics entirely). Averages are computed over at most this many latest
    # articles, which keeps the cost per viewed account bounded.
    metrics_per_account_limit: int = 10
    # Max concurrent SYNC_METRICS provider calls (across and within accounts).
    # Account aggregates are recomputed once per account after its batch, so
    # intra-account calls can run in parallel without thrashing the account row.
    # Bounded to respect the provider's rate limit (tune to qovia's real limit).
    metrics_concurrency: int = 6
    # Live content search via qovia ``/v1/search`` — used as a fallback so a
    # keyword that matches articles (but no account) still returns results
    # instead of an empty page. Cached briefly to avoid repeat paid calls.
    content_search_live_enabled: bool = True
    content_search_page_size: int = 20
    content_search_cache_ttl_seconds: int = 600
    # Circuit breaker for the (billed, often-empty) account-search endpoint: after
    # N consecutive empty results, skip the paid call for the cooldown window.
    account_search_breaker_threshold: int = 3
    account_search_breaker_cooldown_seconds: int = 900
    # Per-call provider HTTP timeout / retry budget. Kept modest so an interactive
    # search fails fast instead of hanging on a slow upstream.
    provider_timeout_seconds: float = 15.0
    provider_max_retries: int = 1
    # The standalone worker is the primary consumer of demand jobs. When it is
    # not running (e.g. local dev that only starts the API), the API drains a
    # bounded batch after responding to a search/detail request so the feature
    # still works end to end. Job claiming is atomic, so running this alongside
    # the worker never double-processes. 0 disables the in-process drain.
    on_demand_inline_drain_max_jobs: int = 60
    # Backlog throttling for a manual drain: when the SYNC_METRICS queue is
    # backed up, shrink the per-drain batch so a single click can't trigger a
    # large charge. Only applies when the caller doesn't pass an explicit cap.
    metrics_backlog_threshold: int = 100
    metrics_backlog_throttled_max_jobs: int = 30

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
    # Allow the mock QR login even when APP_ENV=production (local demos only).
    # Defaults to off so a real deployment never silently falls back to mock.
    wechat_mock_enabled: bool = False
    # Onboarding proof uploads.
    proof_max_mb: int = 5
    upload_dir: str = ""
    # Whether proof is required when submitting onboarding. Off during local /
    # gray-rollout testing so users can validate the site flow; flip to true
    # before production launch.
    onboarding_proof_required: bool = False
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
        search_retry_max_attempts=_int(os.getenv("SEARCH_RETRY_MAX_ATTEMPTS"), 8),
        search_retry_base_seconds=_int(os.getenv("SEARCH_RETRY_BASE_SECONDS"), 60),
        search_retry_interval_seconds=_int(os.getenv("SEARCH_RETRY_INTERVAL_SECONDS"), 30),
        search_retry_enabled=_bool(os.getenv("SEARCH_RETRY_ENABLED"), False),
        collection_enabled=_bool(os.getenv("COLLECTION_ENABLED"), False),
        metrics_min_interval_hours=_int(os.getenv("METRICS_MIN_INTERVAL_HOURS"), 24),
        on_demand_sync_enabled=_bool(os.getenv("ON_DEMAND_SYNC_ENABLED"), True),
        on_demand_sync_ttl_hours=_int(os.getenv("ON_DEMAND_SYNC_TTL_HOURS"), 12),
        article_sync_max_pages=_int(os.getenv("ARTICLE_SYNC_MAX_PAGES"), 1),
        metrics_per_account_limit=_int(os.getenv("METRICS_PER_ACCOUNT_LIMIT"), 10),
        metrics_concurrency=_int(os.getenv("METRICS_CONCURRENCY"), 6),
        content_search_live_enabled=_bool(os.getenv("CONTENT_SEARCH_LIVE_ENABLED"), True),
        content_search_page_size=_int(os.getenv("CONTENT_SEARCH_PAGE_SIZE"), 20),
        content_search_cache_ttl_seconds=_int(
            os.getenv("CONTENT_SEARCH_CACHE_TTL_SECONDS"), 600
        ),
        account_search_breaker_threshold=_int(
            os.getenv("ACCOUNT_SEARCH_BREAKER_THRESHOLD"), 3
        ),
        account_search_breaker_cooldown_seconds=_int(
            os.getenv("ACCOUNT_SEARCH_BREAKER_COOLDOWN_SECONDS"), 900
        ),
        provider_timeout_seconds=_float(os.getenv("PROVIDER_TIMEOUT_SECONDS"), 15.0),
        provider_max_retries=_int(os.getenv("PROVIDER_MAX_RETRIES"), 1),
        on_demand_inline_drain_max_jobs=_int(
            os.getenv("ON_DEMAND_INLINE_DRAIN_MAX_JOBS"), 60
        ),
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
        wechat_mock_enabled=_bool(os.getenv("WECHAT_MOCK_ENABLED"), False),
        proof_max_mb=_int(os.getenv("PROOF_MAX_MB"), 5),
        upload_dir=os.getenv("UPLOAD_DIR") or str(BACKEND_DIR / "uploads"),
        onboarding_proof_required=_bool(os.getenv("ONBOARDING_PROOF_REQUIRED"), False),
        admin_phone=os.getenv("ADMIN_PHONE", ""),
        admin_password=os.getenv("ADMIN_PASSWORD", ""),
    )
