"""Aggregate router for /api/v1."""

from fastapi import APIRouter

from app.api.v1 import accounts, articles

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(accounts.router)
api_router.include_router(articles.router)
