"""Aggregate router for /api/v1."""

from fastapi import APIRouter

from app.api.v1 import accounts, admin, articles, auth, onboarding, overview, selection

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(onboarding.router)
api_router.include_router(overview.router)
api_router.include_router(accounts.router)
api_router.include_router(articles.router)
api_router.include_router(selection.router)
api_router.include_router(admin.router)
