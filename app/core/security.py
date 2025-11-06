"""Security and authentication middleware."""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware to validate API key if configured."""

    async def dispatch(self, request: Request, call_next):
        """Validate API key for protected endpoints."""
        # Skip auth for health check and docs endpoints
        if request.url.path in ["/", "/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        # Only enforce auth if API_KEY is configured
        if settings.api_key:
            api_key = request.headers.get("X-API-Key")

            if not api_key:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": (
                            "Missing X-API-Key header. Please provide API key for authentication."
                        )
                    },
                )

            if api_key != settings.api_key:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid API key. Please check your X-API-Key header."},
                )

        return await call_next(request)
