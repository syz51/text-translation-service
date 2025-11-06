"""Health check endpoints."""

from fastapi import APIRouter, Response

from app.core.config import settings
from app.schemas import HealthResponse
from app.services.assemblyai_client import assemblyai_client
from app.storage.s3 import s3_storage

router = APIRouter()


@router.get("/", response_model=HealthResponse)
@router.get("/health", response_model=HealthResponse)
async def health_check(response: Response):
    """Health check endpoint with detailed component tests.

    Tests connectivity for all critical components: AssemblyAI, S3 storage.
    Returns 503 status code when any component is unhealthy (degraded state).

    Args:
        response: FastAPI Response object for setting status code

    Returns:
        HealthResponse: Service health status with component details
    """
    components = {}

    # Test AssemblyAI connectivity
    assemblyai_ok = await assemblyai_client.test_connectivity()
    components["assemblyai"] = {
        "status": "healthy" if assemblyai_ok else "unhealthy",
        "message": "API key valid, connection OK" if assemblyai_ok else "API connection failed",
    }

    # Test S3 connectivity
    s3_ok = await s3_storage.test_connectivity()
    components["s3_storage"] = {
        "status": "healthy" if s3_ok else "unhealthy",
        "message": "Bucket accessible" if s3_ok else "Bucket connection failed",
    }

    # Determine overall status
    all_healthy = assemblyai_ok and s3_ok
    status = "running" if all_healthy else "degraded"

    # Set 503 status code if any service is degraded
    if not all_healthy:
        response.status_code = 503

    return HealthResponse(
        service=settings.app_name,
        status=status,
        version=settings.app_version,
        authentication="enabled" if settings.api_key else "disabled",
        components=components,
    )
