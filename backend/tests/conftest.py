"""Pytest fixtures: isolated SQLite DB, sessions and a TestClient."""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

# Make backend and repo-root packages importable before app modules load.
BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
for path in (str(BACKEND_DIR), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

# Point the app at a throwaway SQLite file *before* importing app modules.
_DB_FILE = Path(tempfile.gettempdir()) / "wechat_insight_pytest.db"
os.environ.setdefault("APP_ENV", "test")
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_DB_FILE}"
os.environ.setdefault("DEFAULT_PROVIDER", "mock")
os.environ.setdefault("ALLOW_COLD_START_SEARCH", "true")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.ratelimit import rate_limiter  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db() -> Iterator[None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    rate_limiter.reset()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session() -> Iterator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
