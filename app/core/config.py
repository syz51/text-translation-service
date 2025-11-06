"""Application configuration management."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    app_name: str = "Text Translation Service"
    app_version: str = "0.1.0"
    app_description: str = "Translate SRT subtitle files using Google GenAI (Gemini 2.5 Pro)"

    # Environment
    environment: str = "development"  # development, staging, production

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    allowed_hosts: list[str] = ["*"]

    # Authentication
    api_key: str | None = None

    # CORS Configuration
    cors_enabled: bool = True
    cors_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    # Google GenAI Configuration
    google_api_key: str
    default_model: str = "gemini-2.5-pro"

    # Translation Configuration
    default_chunk_size: int = 100
    max_concurrent_requests: int = 25

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


# Global settings instance
settings = Settings()
