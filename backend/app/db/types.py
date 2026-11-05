"""Portable column types.

Production uses PostgreSQL (BIGSERIAL, TIMESTAMPTZ). Tests use SQLite, where a
BIGINT primary key does not autoincrement; ``bigint_pk`` degrades to INTEGER on
SQLite so the same models work in both places.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, DateTime, Integer


def bigint_pk():
    return BigInteger().with_variant(Integer, "sqlite")


def timestamptz():
    return DateTime(timezone=True)
