"""FastAPI application factory and configuration."""

from contextlib import asynccontextmanager
import logging
from pathlib import Path
import subprocess

from fastapi import FastAPI

from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import setup_middleware

# Setup logging
setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Application startup: Initializing database")

    # Create data directory if it doesn't exist
    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)
    logger.info(f"Data directory ready: {data_dir.absolute()}")

    # Run Alembic migrations
    try:
        logger.info("Running database migrations")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(f"Migrations completed successfully: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Migration failed: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error running migrations: {e}")
        raise

    yield

    # Shutdown
    logger.info("Application shutdown")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
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

    uvicorn.run(
        "app.main:app", host=settings.host, port=settings.port, proxy_headers=True, reload=False
    )
