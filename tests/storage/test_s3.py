"""Unit tests for S3 storage."""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

from botocore.exceptions import ClientError
import pytest

from app.core.config import Settings
from app.storage.s3 import S3ClientNotInitializedError, S3Storage


class TestS3StorageInitialization:
    """Test S3Storage initialization."""

    @patch("app.storage.s3.get_settings")
    def test_init(self, mock_get_settings):
        """Test basic initialization."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_region="us-east-1",
            s3_access_key_id="test-key",
            s3_secret_access_key="test-secret",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        assert storage.bucket == "test-bucket"
        assert storage.region == "us-east-1"
        assert storage._client is None
        assert storage._client_context is None

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_initialize_success(self, mock_get_settings):
        """Test successful S3 client initialization."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_region="us-east-1",
            s3_access_key_id="test-key",
            s3_secret_access_key="test-secret",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        # Mock aioboto3 session
        mock_client = AsyncMock()
        mock_client.head_bucket = AsyncMock()

        mock_client_context = AsyncMock()
        mock_client_context.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_context.__aexit__ = AsyncMock()

        storage.session.client = MagicMock(return_value=mock_client_context)

        result = await storage.initialize()

        assert result is True
        assert storage._client is not None
        mock_client.head_bucket.assert_called_once_with(Bucket="test-bucket")

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_initialize_client_error(self, mock_get_settings):
        """Test initialization failure with ClientError."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_region="us-east-1",
            s3_access_key_id="bad-key",
            s3_secret_access_key="bad-secret",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        mock_client = AsyncMock()
        mock_client.head_bucket = AsyncMock(side_effect=ClientError({}, "HeadBucket"))

        mock_client_context = AsyncMock()
        mock_client_context.__aenter__ = AsyncMock(return_value=mock_client)

        storage.session.client = MagicMock(return_value=mock_client_context)

        result = await storage.initialize()

        assert result is False
        assert storage._client is None

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_initialize_generic_error(self, mock_get_settings):
        """Test initialization failure with generic exception."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_region="us-east-1",
            s3_access_key_id="test-key",
            s3_secret_access_key="test-secret",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        storage.session.client = MagicMock(side_effect=RuntimeError("Network error"))

        result = await storage.initialize()

        assert result is False
        assert storage._client is None

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_close(self, mock_get_settings):
        """Test closing S3 client."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        # Simulate initialized client
        mock_client = AsyncMock()
        mock_client_context = AsyncMock()
        mock_client_context.__aexit__ = AsyncMock()

        storage._client = mock_client
        storage._client_context = mock_client_context

        await storage.close()

        assert storage._client is None
        assert storage._client_context is None
        mock_client_context.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_close_with_error(self, mock_get_settings):
        """Test closing S3 client when error occurs."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        mock_client = AsyncMock()
        mock_client_context = AsyncMock()
        mock_client_context.__aexit__ = AsyncMock(side_effect=RuntimeError("Close error"))

        storage._client = mock_client
        storage._client_context = mock_client_context

        await storage.close()

        # Should still cleanup even with error
        assert storage._client is None
        assert storage._client_context is None


class TestEnsureInitialized:
    """Test _ensure_initialized method."""

    @patch("app.storage.s3.get_settings")
    def test_ensure_initialized_success(self, mock_get_settings):
        """Test ensure initialized when client exists."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()
        storage._client = AsyncMock()

        # Should not raise
        storage._ensure_initialized()

    @patch("app.storage.s3.get_settings")
    def test_ensure_initialized_not_initialized(self, mock_get_settings):
        """Test ensure initialized when client not initialized."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        with pytest.raises(S3ClientNotInitializedError, match="not initialized"):
            storage._ensure_initialized()


class TestUploadAudio:
    """Test upload_audio method."""

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_upload_audio_success(self, mock_get_settings):
        """Test successful audio upload."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        mock_client = AsyncMock()
        mock_client.upload_fileobj = AsyncMock()
        storage._client = mock_client

        # Create mock UploadFile
        mock_file = MagicMock()
        mock_file.filename = "test.mp3"
        mock_file.content_type = "audio/mpeg"
        mock_file.file = BytesIO(b"fake audio data")
        mock_file.seek = AsyncMock()

        result = await storage.upload_audio("job-123", mock_file)

        assert result == "audio/job-123/test.mp3"
        mock_client.upload_fileobj.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_upload_audio_not_initialized(self, mock_get_settings):
        """Test upload audio when client not initialized."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        mock_file = MagicMock()
        mock_file.filename = "test.mp3"

        with pytest.raises(S3ClientNotInitializedError):
            await storage.upload_audio("job-123", mock_file)

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_upload_audio_failure(self, mock_get_settings):
        """Test upload audio failure."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        mock_client = AsyncMock()
        mock_client.upload_fileobj = AsyncMock(side_effect=RuntimeError("Upload failed"))
        storage._client = mock_client

        mock_file = MagicMock()
        mock_file.filename = "test.mp3"
        mock_file.content_type = "audio/mpeg"
        mock_file.file = BytesIO(b"fake audio data")
        mock_file.seek = AsyncMock()

        with pytest.raises(RuntimeError, match="Upload failed"):
            await storage.upload_audio("job-123", mock_file)


class TestUploadSRT:
    """Test upload_srt method."""

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_upload_srt_success(self, mock_get_settings):
        """Test successful SRT upload."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        mock_client = AsyncMock()
        mock_client.put_object = AsyncMock()
        storage._client = mock_client

        srt_content = "1\n00:00:00,000 --> 00:00:01,000\nTest"
        result = await storage.upload_srt("job-123", srt_content)

        assert result == "srt/job-123.srt"
        mock_client.put_object.assert_called_once()
        call_args = mock_client.put_object.call_args
        assert call_args[1]["Key"] == "srt/job-123.srt"
        assert call_args[1]["ContentType"] == "text/plain; charset=utf-8"

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_upload_srt_not_initialized(self, mock_get_settings):
        """Test upload SRT when client not initialized."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        with pytest.raises(S3ClientNotInitializedError):
            await storage.upload_srt("job-123", "test content")

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_upload_srt_failure(self, mock_get_settings):
        """Test upload SRT failure."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        mock_client = AsyncMock()
        mock_client.put_object = AsyncMock(side_effect=RuntimeError("Upload failed"))
        storage._client = mock_client

        with pytest.raises(RuntimeError, match="Upload failed"):
            await storage.upload_srt("job-123", "test content")


class TestGeneratePresignedURL:
    """Test generate_presigned_url method."""

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_generate_presigned_url_success(self, mock_get_settings):
        """Test successful presigned URL generation."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        mock_client = AsyncMock()
        mock_client.generate_presigned_url = AsyncMock(
            return_value="https://test-bucket.s3.amazonaws.com/srt/test.srt?signature=abc123"
        )
        storage._client = mock_client

        result = await storage.generate_presigned_url("srt/test.srt", 3600)

        assert "https://" in result
        assert "srt/test.srt" in result
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "srt/test.srt"},
            ExpiresIn=3600,
        )

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_generate_presigned_url_not_initialized(self, mock_get_settings):
        """Test presigned URL generation when client not initialized."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        with pytest.raises(S3ClientNotInitializedError):
            await storage.generate_presigned_url("srt/test.srt", 3600)

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_generate_presigned_url_failure(self, mock_get_settings):
        """Test presigned URL generation failure."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        mock_client = AsyncMock()
        mock_client.generate_presigned_url = AsyncMock(side_effect=RuntimeError("URL gen failed"))
        storage._client = mock_client

        with pytest.raises(RuntimeError, match="URL gen failed"):
            await storage.generate_presigned_url("srt/test.srt", 3600)


class TestConnectivity:
    """Test test_connectivity method."""

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_connectivity_success(self, mock_get_settings):
        """Test successful connectivity check."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        mock_client = AsyncMock()
        mock_client.head_bucket = AsyncMock()
        storage._client = mock_client

        result = await storage.test_connectivity()

        assert result is True
        mock_client.head_bucket.assert_called_once_with(Bucket="test-bucket")

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_connectivity_not_initialized(self, mock_get_settings):
        """Test connectivity check when client not initialized."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        result = await storage.test_connectivity()

        assert result is False

    @pytest.mark.asyncio
    @patch("app.storage.s3.get_settings")
    async def test_connectivity_failure(self, mock_get_settings):
        """Test connectivity check failure."""
        mock_settings = Settings(
            s3_bucket_name="test-bucket",
            s3_max_pool_connections=10,
            s3_connect_timeout=5,
            s3_read_timeout=60,
        )
        mock_get_settings.return_value = mock_settings

        storage = S3Storage()

        mock_client = AsyncMock()
        mock_client.head_bucket = AsyncMock(side_effect=ClientError({}, "HeadBucket"))
        storage._client = mock_client

        result = await storage.test_connectivity()

        assert result is False
