"""API v1 package initialization."""

from fastapi import APIRouter

from app.api.v1 import health, translation

# Create v1 router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health.router, tags=["health"])
api_router.include_router(translation.router, prefix="/translate", tags=["translation"])

__all__ = ["api_router"]
