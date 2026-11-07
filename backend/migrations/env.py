"""Alembic environment configuration."""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings  # noqa: E402
from app.db import models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402

config = context.config


def _migration_url() -> str:
    """Use DIRECT_DATABASE_URL (Neon direct, bypasses PgBouncer) on Postgres only.

    Falls back to DATABASE_URL otherwise (e.g. local SQLite). The scheme is
    normalized to the psycopg3 driver we ship, so a `+psycopg2` DSN works
    without installing psycopg2. `%` is escaped because ConfigParser treats it
    as interpolation (e.g. Neon's `options=...%3D...`).
    """
    base = get_settings().database_url
    direct = os.getenv("DIRECT_DATABASE_URL", "").strip()
    url = direct if (direct and base.startswith("postgresql")) else base
    url = url.replace("postgresql+psycopg2://", "postgresql+psycopg://")
    return url.replace("%", "%%")


config.set_main_option("sqlalchemy.url", _migration_url())

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
