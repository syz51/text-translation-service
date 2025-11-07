"""S3 storage wrapper for audio and SRT files."""

import logging
from typing import Any

import aioboto3
from botocore.client import Config
from botocore.exceptions import ClientError
from fastapi import UploadFile

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class S3ClientNotInitializedError(Exception):
    """Raised when S3 client is used before initialization."""

    pass


class S3Storage:
    """S3 storage client with connection pooling for managing audio and SRT files.

    This class uses a long-lived aioboto3 client with connection pooling for
    production-grade performance. The client must be initialized with initialize()
    before use and closed with close() on shutdown.
    """

    def __init__(self, settings: Settings | None = None):
        """Initialize S3 storage configuration (does not create client).

        Args:
            settings: Optional Settings instance (uses get_settings() if not provided)
        """
        if settings is None:
            settings = get_settings()

        self.session = aioboto3.Session()
        self.bucket = settings.s3_bucket_name
        self.endpoint_url = settings.s3_endpoint_url
        self.region = settings.s3_region
        self.access_key = settings.s3_access_key_id
        self.secret_key = settings.s3_secret_access_key

        # Connection pool configuration
        self.config = Config(
            max_pool_connections=settings.s3_max_pool_connections,
            connect_timeout=settings.s3_connect_timeout,
            read_timeout=settings.s3_read_timeout,
            retries={
                "max_attempts": 3,
                "mode": "adaptive",
            },
        )

        # Store settings for later use (e.g., in initialize())
        self._settings = settings

        # Long-lived client (initialized in initialize())
        self._client: Any = None
        self._client_context: Any = None

    async def initialize(self) -> bool:
        """Initialize long-lived S3 client with connection pooling.

        Must be called before using any S3 operations. Typically called
        during application startup.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Create long-lived client with connection pooling
            self._client_context = self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                config=self.config,
            )
            self._client = await self._client_context.__aenter__()

            # Test connectivity with HEAD bucket
            await self._client.head_bucket(Bucket=self.bucket)
            logger.info(
                "S3 client initialized successfully with connection pool (max_connections=%d)",
                self._settings.s3_max_pool_connections,
            )
            return True
        except ClientError as e:
            logger.error("Failed to initialize S3 client: %s", e)
            # Properly cleanup client if __aenter__ was called
            if self._client_context is not None:
                try:
                    await self._client_context.__aexit__(None, None, None)
                except Exception:
                    pass  # Already in error state, ignore cleanup errors
            self._client = None
            self._client_context = None
            return False
        except Exception as e:
            logger.error("Unexpected error initializing S3 client: %s", e)
            # Properly cleanup client if __aenter__ was called
            if self._client_context is not None:
                try:
                    await self._client_context.__aexit__(None, None, None)
                except Exception:
                    pass  # Already in error state, ignore cleanup errors
            self._client = None
            self._client_context = None
            return False

    async def close(self) -> None:
        """Close S3 client and cleanup connections.

        Should be called during application shutdown.
        """
        if self._client_context is not None:
            try:
                await self._client_context.__aexit__(None, None, None)
                logger.info("S3 client closed successfully")
            except Exception as e:
                logger.error("Error closing S3 client: %s", e)
            finally:
                self._client = None
                self._client_context = None

    def _ensure_initialized(self) -> None:
        """Ensure client is initialized before operations.

        Raises:
            S3ClientNotInitializedError: If client not initialized
        """
        if self._client is None:
            raise S3ClientNotInitializedError("S3 client not initialized. Call initialize() first.")

    async def upload_audio(self, job_id: str, file: UploadFile) -> str:
        """Upload audio file to S3.

        Args:
            job_id: Job ID for organizing files
            file: Audio file to upload

        Returns:
            S3 key for the uploaded file

        Raises:
            S3ClientNotInitializedError: If client not initialized
            Exception: If upload fails
        """
        self._ensure_initialized()
        s3_key = f"audio/{job_id}/{file.filename}"

        try:
            # Stream upload the file using pooled client
            await self._client.upload_fileobj(
                file.file,
                self.bucket,
                s3_key,
                ExtraArgs={"ContentType": file.content_type or "audio/mpeg"},
            )

            logger.info("Uploaded audio file to S3: %s", s3_key)
            return s3_key
        except Exception as e:
            logger.error("Failed to upload audio file to S3: %s", e)
            raise
        finally:
            # Ensure file handle is properly managed
            try:
                await file.seek(0)
            except Exception:
                pass  # File might not support seek or already closed

    async def upload_srt(self, job_id: str, content: str) -> str:
        """Upload SRT file to S3.

        Args:
            job_id: Job ID for organizing files
            content: SRT file content as string

        Returns:
            S3 key for the uploaded file

        Raises:
            S3ClientNotInitializedError: If client not initialized
            Exception: If upload fails
        """
        self._ensure_initialized()
        s3_key = f"srt/{job_id}.srt"

        try:
            # Upload SRT content as bytes using pooled client
            await self._client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=content.encode("utf-8"),
                ContentType="text/plain; charset=utf-8",
            )

            logger.info("Uploaded SRT file to S3: %s", s3_key)
            return s3_key
        except Exception as e:
            logger.error("Failed to upload SRT file to S3: %s", e)
            raise

    async def generate_presigned_url(self, s3_key: str, expiry: int) -> str:
        """Generate presigned URL for S3 object.

        Args:
            s3_key: S3 object key
            expiry: URL expiry time in seconds

        Returns:
            Presigned URL

        Raises:
            S3ClientNotInitializedError: If client not initialized
            Exception: If URL generation fails
        """
        self._ensure_initialized()

        try:
            url = await self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": s3_key},
                ExpiresIn=expiry,
            )

            logger.info("Generated presigned URL for %s (expires in %ss)", s3_key, expiry)
            return url
        except Exception as e:
            logger.error("Failed to generate presigned URL: %s", e)
            raise

    async def test_connectivity(self) -> bool:
        """Test S3 connectivity with HEAD request to bucket.

        Returns:
            True if client initialized and connection successful, False otherwise
        """
        if self._client is None:
            logger.error("S3 connectivity test failed: client not initialized")
            return False

        try:
            await self._client.head_bucket(Bucket=self.bucket)
            return True
        except Exception as e:
            logger.error("S3 connectivity test failed: %s", e)
            return False


# Global S3 storage instance
s3_storage = S3Storage()
