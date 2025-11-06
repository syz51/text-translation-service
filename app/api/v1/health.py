"""Health check endpoints."""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas import HealthResponse

router = APIRouter()


@router.get("/", response_model=HealthResponse)
@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint.

    Returns:
        HealthResponse: Service health status information
    """
    return HealthResponse(
        service=settings.app_name,
        status="running",
        version=settings.app_version,
        authentication="enabled" if settings.api_key else "disabled",
    )
