"""Middleware configuration."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.core.security import AuthenticationMiddleware


def setup_middleware(app: FastAPI) -> None:
    """Configure all middleware for the application.

    Args:
        app: FastAPI application instance
    """
    # CORS middleware
    if settings.cors_enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=settings.cors_allow_methods,
            allow_headers=settings.cors_allow_headers,
        )

    # GZip compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Trusted host middleware (production security)
    if settings.environment == "production" and settings.allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_hosts,
        )

    # Authentication middleware
    app.add_middleware(AuthenticationMiddleware)
