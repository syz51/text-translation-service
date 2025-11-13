"""FastAPI application factory and configuration."""

from contextlib import asynccontextmanager
import logging
import subprocess

from fastapi import FastAPI

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.middleware import setup_middleware
from app.services.polling_service import polling_service
from app.storage.s3 import s3_storage

# Setup logging
setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Application startup: Initializing services")

    # Run Alembic migrations
    try:
        logger.info("Running database migrations")
        subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info("Migrations completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error("Migration failed: %s", e.stderr)
        raise
    except Exception as e:
        logger.error("Unexpected error running migrations: %s", e)
        raise

    # Initialize S3 storage with connection pooling
    try:
        logger.info("Initializing S3 storage client")
        s3_initialized = await s3_storage.initialize()
        if not s3_initialized:
            logger.warning("S3 storage initialization failed - storage operations will not work")
        else:
            logger.info("S3 storage client initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize S3 storage: %s", e)
        # Don't raise - allow app to start even if S3 fails
        logger.warning("Application starting without S3 connectivity")

    # Start polling service for stale job recovery
    try:
        await polling_service.start()
    except Exception as e:
        logger.error("Failed to start polling service: %s", e)
        # Don't raise - allow app to start even if polling fails

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Application shutdown: Cleaning up resources")

    # Stop polling service
    try:
        await polling_service.stop()
    except Exception as e:
        logger.error("Error stopping polling service: %s", e)

    # Close S3 client
    try:
        await s3_storage.close()
    except Exception as e:
        logger.error("Error closing S3 storage: %s", e)

    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Setup middleware (CORS, auth, etc.)
    setup_middleware(app)

    # Include API routes with versioning
    app.include_router(api_router, prefix="/api/v1")

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app", host=settings.host, port=settings.port, proxy_headers=True, reload=False
    )
