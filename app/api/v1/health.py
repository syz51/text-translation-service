"""Health check endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.config import Settings, get_settings
from app.schemas import HealthResponse
from app.services.assemblyai_client import assemblyai_client
from app.storage.s3 import s3_storage

router = APIRouter()


@router.get("/", response_model=HealthResponse)
@router.get("/health", response_model=HealthResponse)
async def health_check(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
):
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

    # API endpoints info
    endpoints = {
        "translation": [
            "POST /api/v1/translate - Translate SRT files",
        ],
        "transcription": [
            "POST /api/v1/transcriptions - Upload audio and create transcription job",
            "GET /api/v1/transcriptions/{job_id} - Get job status",
            "GET /api/v1/transcriptions/{job_id}/srt - Download SRT file (302 redirect)",
        ],
        "health": [
            "GET /api/v1/health - Service health check with component status",
        ],
    }

    return HealthResponse(
        service=settings.app_name,
        status=status,
        version=settings.app_version,
        authentication="enabled" if settings.api_key else "disabled",
        components=components,
        endpoints=endpoints,
    )
