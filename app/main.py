"""FastAPI application factory and configuration."""

from fastapi import FastAPI

from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import setup_middleware

# Setup logging
setup_logging()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
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
