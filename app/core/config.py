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

    # Database Configuration
    database_path: str = "./data/transcriptions.db"

    # AssemblyAI Configuration
    assemblyai_api_key: str | None = None

    # Webhook Configuration
    webhook_base_url: str | None = None
    webhook_secret_token: str | None = None

    # S3 Configuration
    s3_endpoint_url: str = "https://s3.amazonaws.com"
    s3_region: str = "us-east-1"
    s3_bucket_name: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_max_pool_connections: int = 10  # Connection pool size
    s3_connect_timeout: int = 60  # Connection timeout in seconds
    s3_read_timeout: int = 60  # Read timeout in seconds

    # Transcription Limits
    max_file_size: int = 1_073_741_824  # 1GB in bytes
    max_audio_duration: int = 14_400  # 4 hours in seconds
    max_concurrent_jobs: int = 10
    audio_presigned_url_expiry: int = 86_400  # 24 hours in seconds (ensures AssemblyAI can access)
    srt_presigned_url_expiry: int = 3_600  # 1 hour in seconds
    retry_max_attempts: int = 3
    retry_backoff: list[int] = [1, 5, 15]  # seconds
    webhook_timeout: int = 10  # seconds
    allowed_audio_formats: set[str] = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}

    # Polling/Recovery Configuration
    polling_enabled: bool = True  # Enable background polling for stale jobs
    polling_interval: int = 300  # 5 minutes in seconds
    stale_job_threshold: int = 7200  # 2 hours in seconds

    # Logging
    log_level: str = "INFO"
    enable_log_redaction: bool = True  # Redact sensitive data from logs

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


# Global settings instance
# Pydantic Settings loads from environment variables automatically
settings = Settings()  # type: ignore[call-arg]
