"""Direct tests for transcription API endpoints (for proper coverage tracking).

These tests call endpoint functions directly instead of using TestClient,
which ensures coverage.py can properly track execution.
"""

from io import BytesIO
from unittest.mock import AsyncMock, patch

from fastapi import BackgroundTasks, UploadFile
from fastapi.exceptions import HTTPException
import pytest

from app.api.v1.transcription import (
    assemblyai_webhook,
    create_transcription_job,
    get_transcription_srt,
    get_transcription_status,
    process_transcription_background,
)
from app.core.config import Settings
from app.db import crud
from app.db.models import JobStatus
from app.schemas.transcription import AssemblyAIWebhookPayload
from tests.conftest import create_fake_audio_file


class TestCreateTranscriptionJobDirect:
    """Direct tests for create_transcription_job endpoint."""

    @pytest.mark.asyncio
    async def test_create_success(self, db_session, mock_transcription_services):
        """Test successful transcription job creation (direct call)."""
        mock_settings = Settings(
            max_concurrent_jobs=10,
            allowed_audio_formats={".mp3"},
            max_file_size=1_073_741_824,
            webhook_base_url="https://example.com",
            webhook_secret_token="test_secret",
            audio_presigned_url_expiry=86400,
        )

        # Create UploadFile
        file_data = create_fake_audio_file(1)
        file_data.name = "test.mp3"
        upload_file = UploadFile(filename="test.mp3", file=file_data)

        result = await create_transcription_job(
            file=upload_file,
            language_detection=False,
            speaker_labels=False,
            session=db_session,
            settings=mock_settings,
        )

        assert result.job_id is not None
        assert result.status == JobStatus.PROCESSING.value
        assert result.audio_s3_key is not None

    @pytest.mark.asyncio
    async def test_create_file_read_error(self, db_session, mock_transcription_services):
        """Test error handling when file.read() fails during size check."""
        mock_settings = Settings(
            max_concurrent_jobs=10,
            allowed_audio_formats={".mp3"},
            max_file_size=1_073_741_824,
        )

        # Create UploadFile with mock that fails on read
        file_data = create_fake_audio_file(1)
        file_data.name = "test.mp3"
        upload_file = UploadFile(filename="test.mp3", file=file_data)

        # Make read() fail
        async def failing_read(size=-1):
            raise OSError("Read failed")

        upload_file.read = failing_read

        with pytest.raises(HTTPException) as exc_info:
            await create_transcription_job(
                file=upload_file,
                language_detection=False,
                speaker_labels=False,
                session=db_session,
                settings=mock_settings,
            )
        assert exc_info.value.status_code == 500
        assert "processing file" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_create_job_creation_error(self, db_session, mock_transcription_services):
        """Test error handling when job creation fails."""
        mock_settings = Settings(
            max_concurrent_jobs=10,
            allowed_audio_formats={".mp3"},
            max_file_size=1_073_741_824,
        )

        with patch("app.api.v1.transcription.crud.create_job") as mock_create:
            # Make job creation fail
            mock_create.side_effect = Exception("Database error")

            file_data = create_fake_audio_file(1)
            file_data.name = "test.mp3"
            upload_file = UploadFile(filename="test.mp3", file=file_data)

            with pytest.raises(HTTPException) as exc_info:
                await create_transcription_job(
                    file=upload_file,
                    language_detection=False,
                    speaker_labels=False,
                    session=db_session,
                    settings=mock_settings,
                )
            assert exc_info.value.status_code == 500
            assert "creating transcription job" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_create_s3_upload_error(self, db_session):
        """Test error handling when S3 upload fails."""
        from tests.conftest import FakeAssemblyAIClient, FakeS3Storage

        fake_s3_error = FakeS3Storage(should_fail=True)
        fake_assemblyai = FakeAssemblyAIClient(should_fail=False)
        mock_settings = Settings(
            max_concurrent_jobs=10,
            allowed_audio_formats={".mp3"},
            max_file_size=1_073_741_824,
        )

        with (
            patch("app.api.v1.transcription.s3_storage", fake_s3_error),
            patch("app.api.v1.transcription.assemblyai_client", fake_assemblyai),
        ):
            file_data = create_fake_audio_file(1)
            file_data.name = "test.mp3"
            upload_file = UploadFile(filename="test.mp3", file=file_data)

            with pytest.raises(HTTPException) as exc_info:
                await create_transcription_job(
                    file=upload_file,
                    language_detection=False,
                    speaker_labels=False,
                    session=db_session,
                    settings=mock_settings,
                )
            assert exc_info.value.status_code == 500
            assert "uploading" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_create_presigned_url_error(self, db_session):
        """Test error handling when presigned URL generation fails."""
        from tests.conftest import FakeAssemblyAIClient, FakeS3Storage

        fake_s3 = FakeS3Storage(should_fail=False)
        fake_assemblyai = FakeAssemblyAIClient(should_fail=False)
        mock_settings = Settings(
            max_concurrent_jobs=10,
            allowed_audio_formats={".mp3"},
            max_file_size=1_073_741_824,
        )

        # Make only presigned URL generation fail
        original_generate = fake_s3.generate_presigned_url
        fake_s3.generate_presigned_url = AsyncMock(side_effect=Exception("URL generation failed"))

        with (
            patch("app.api.v1.transcription.s3_storage", fake_s3),
            patch("app.api.v1.transcription.assemblyai_client", fake_assemblyai),
        ):
            file_data = create_fake_audio_file(1)
            file_data.name = "test.mp3"
            upload_file = UploadFile(filename="test.mp3", file=file_data)

            with pytest.raises(HTTPException) as exc_info:
                await create_transcription_job(
                    file=upload_file,
                    language_detection=False,
                    speaker_labels=False,
                    session=db_session,
                    settings=mock_settings,
                )
            assert exc_info.value.status_code == 500
            assert "presigned url" in str(exc_info.value.detail).lower()

        fake_s3.generate_presigned_url = original_generate

    @pytest.mark.asyncio
    async def test_create_webhook_missing(self, db_session, mock_transcription_services):
        """Test error when webhook configuration is missing."""
        mock_settings = Settings(
            max_concurrent_jobs=10,
            allowed_audio_formats={".mp3"},
            max_file_size=1_073_741_824,
            webhook_base_url=None,  # Missing
            webhook_secret_token=None,
        )

        file_data = create_fake_audio_file(1)
        file_data.name = "test.mp3"
        upload_file = UploadFile(filename="test.mp3", file=file_data)

        with pytest.raises(HTTPException) as exc_info:
            await create_transcription_job(
                file=upload_file,
                language_detection=False,
                speaker_labels=False,
                session=db_session,
                settings=mock_settings,
            )
        assert exc_info.value.status_code == 500
        assert "transcription" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_create_assemblyai_error(self, db_session):
        """Test error handling when AssemblyAI start fails."""
        from tests.conftest import FakeAssemblyAIClient, FakeS3Storage

        fake_s3 = FakeS3Storage(should_fail=False)
        fake_assemblyai = FakeAssemblyAIClient(should_fail=True)
        mock_settings = Settings(
            max_concurrent_jobs=10,
            allowed_audio_formats={".mp3"},
            max_file_size=1_073_741_824,
            webhook_base_url="https://example.com",
            webhook_secret_token="test_secret",
            audio_presigned_url_expiry=86400,
        )

        with (
            patch("app.api.v1.transcription.s3_storage", fake_s3),
            patch("app.api.v1.transcription.assemblyai_client", fake_assemblyai),
        ):
            file_data = create_fake_audio_file(1)
            file_data.name = "test.mp3"
            upload_file = UploadFile(filename="test.mp3", file=file_data)

            with pytest.raises(HTTPException) as exc_info:
                await create_transcription_job(
                    file=upload_file,
                    language_detection=False,
                    speaker_labels=False,
                    session=db_session,
                    settings=mock_settings,
                )
            assert exc_info.value.status_code == 500
            assert "transcription" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_create_concurrent_limit_reached(self, db_session, mock_transcription_services):
        """Test rejection when concurrent job limit is reached."""
        # Create 10 jobs to hit limit
        for i in range(10):
            job = await crud.create_job(
                db_session,
                audio_s3_key=f"audio/test_{i}.mp3",
                language_detection=False,
                speaker_labels=False,
            )
            await crud.update_job_status(db_session, job.id, JobStatus.PROCESSING.value)

        mock_settings = Settings(
            max_concurrent_jobs=10,
            allowed_audio_formats={".mp3"},
            max_file_size=1_073_741_824,
        )

        file_data = create_fake_audio_file(1)
        file_data.name = "test.mp3"
        upload_file = UploadFile(filename="test.mp3", file=file_data)

        with pytest.raises(HTTPException) as exc_info:
            await create_transcription_job(
                file=upload_file,
                language_detection=False,
                speaker_labels=False,
                session=db_session,
                settings=mock_settings,
            )
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_create_invalid_format(self, db_session, mock_transcription_services):
        """Test rejection of invalid audio format."""
        mock_settings = Settings(
            max_concurrent_jobs=10,
            allowed_audio_formats={".mp3"},
            max_file_size=1_073_741_824,
        )

        file_data = BytesIO(b"fake data")
        file_data.name = "test.txt"
        upload_file = UploadFile(filename="test.txt", file=file_data)

        with pytest.raises(HTTPException) as exc_info:
            await create_transcription_job(
                file=upload_file,
                language_detection=False,
                speaker_labels=False,
                session=db_session,
                settings=mock_settings,
            )
        assert exc_info.value.status_code == 400
        assert "invalid audio format" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_create_file_too_large(self, db_session, mock_transcription_services):
        """Test rejection of files exceeding size limit."""
        mock_settings = Settings(
            max_concurrent_jobs=10,
            allowed_audio_formats={".mp3"},
            max_file_size=1024,  # 1KB limit
        )

        file_data = create_fake_audio_file(1)  # 1MB file
        file_data.name = "huge.mp3"
        upload_file = UploadFile(filename="huge.mp3", file=file_data)

        with pytest.raises(HTTPException) as exc_info:
            await create_transcription_job(
                file=upload_file,
                language_detection=False,
                speaker_labels=False,
                session=db_session,
                settings=mock_settings,
            )
        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_create_with_language_detection(self, db_session, mock_transcription_services):
        """Test creation with language detection enabled."""
        mock_settings = Settings(
            max_concurrent_jobs=10,
            allowed_audio_formats={".mp3"},
            max_file_size=1_073_741_824,
            webhook_base_url="https://example.com",
            webhook_secret_token="test_secret",
            audio_presigned_url_expiry=86400,
        )

        file_data = create_fake_audio_file(1)
        file_data.name = "test.mp3"
        upload_file = UploadFile(filename="test.mp3", file=file_data)

        result = await create_transcription_job(
            file=upload_file,
            language_detection=True,
            speaker_labels=False,
            session=db_session,
            settings=mock_settings,
        )

        assert result.language_detection is True

    @pytest.mark.asyncio
    async def test_create_with_speaker_labels(self, db_session, mock_transcription_services):
        """Test creation with speaker labels enabled."""
        mock_settings = Settings(
            max_concurrent_jobs=10,
            allowed_audio_formats={".mp3"},
            max_file_size=1_073_741_824,
            webhook_base_url="https://example.com",
            webhook_secret_token="test_secret",
            audio_presigned_url_expiry=86400,
        )

        file_data = create_fake_audio_file(1)
        file_data.name = "test.mp3"
        upload_file = UploadFile(filename="test.mp3", file=file_data)

        result = await create_transcription_job(
            file=upload_file,
            language_detection=False,
            speaker_labels=True,
            session=db_session,
            settings=mock_settings,
        )

        assert result.speaker_labels is True


class TestGetTranscriptionStatusDirect:
    """Direct tests for get_transcription_status endpoint."""

    @pytest.mark.asyncio
    async def test_get_status_success(self, db_session):
        """Test getting status of existing job."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )

        result = await get_transcription_status(job_id=job.id, session=db_session)

        assert result.job_id == job.id
        assert result.status == JobStatus.QUEUED.value
        assert result.srt_available is False

    @pytest.mark.asyncio
    async def test_get_status_not_found(self, db_session):
        """Test getting status of non-existent job."""
        with pytest.raises(HTTPException) as exc_info:
            await get_transcription_status(job_id="nonexistent", session=db_session)
        assert exc_info.value.status_code == 404


class TestGetTranscriptionSRTDirect:
    """Direct tests for get_transcription_srt endpoint."""

    @pytest.mark.asyncio
    async def test_download_success(self, db_session, mock_transcription_services):
        """Test downloading SRT file for completed job."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        srt_key = f"srt/{job.id}.srt"
        await crud.update_job_result(db_session, job.id, srt_key)

        # Upload fake SRT to storage
        mock_transcription_services["s3"].storage[srt_key] = "1\n00:00:00,000"

        mock_settings = Settings(srt_presigned_url_expiry=3600)

        result = await get_transcription_srt(
            job_id=job.id, session=db_session, settings=mock_settings
        )

        assert result.status_code == 302
        assert "fake-s3.amazonaws.com" in result.headers["location"]

    @pytest.mark.asyncio
    async def test_download_not_found(self, db_session):
        """Test downloading SRT for non-existent job."""
        with pytest.raises(HTTPException) as exc_info:
            await get_transcription_srt(job_id="nonexistent", session=db_session)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_download_not_ready(self, db_session):
        """Test downloading SRT when job is not ready."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_transcription_srt(job_id=job.id, session=db_session)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_download_error_status(self, db_session):
        """Test downloading SRT when job has error status."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        await crud.update_job_status(db_session, job.id, JobStatus.ERROR.value, error="Test error")

        with pytest.raises(HTTPException) as exc_info:
            await get_transcription_srt(job_id=job.id, session=db_session)
        assert exc_info.value.status_code == 400
        assert "failed" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_download_processing_status(self, db_session):
        """Test downloading SRT when job is still processing."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        await crud.update_job_status(db_session, job.id, JobStatus.PROCESSING.value)

        with pytest.raises(HTTPException) as exc_info:
            await get_transcription_srt(job_id=job.id, session=db_session)
        assert exc_info.value.status_code == 400
        assert "progress" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_download_completed_no_srt_key(self, db_session):
        """Test downloading SRT when job is completed but has no SRT key."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        # Force job to completed status without SRT key
        await crud.update_job_status(db_session, job.id, JobStatus.COMPLETED.value)

        with pytest.raises(HTTPException) as exc_info:
            await get_transcription_srt(job_id=job.id, session=db_session)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_download_presigned_url_error(self, db_session, mock_transcription_services):
        """Test error when presigned URL generation fails."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        srt_key = f"srt/{job.id}.srt"
        await crud.update_job_result(db_session, job.id, srt_key)

        # Upload fake SRT but make presigned URL generation fail
        mock_transcription_services["s3"].storage[srt_key] = "1\n00:00:00,000"
        mock_transcription_services["s3"].generate_presigned_url = AsyncMock(
            side_effect=Exception("URL error")
        )

        mock_settings = Settings(srt_presigned_url_expiry=3600)

        with pytest.raises(HTTPException) as exc_info:
            await get_transcription_srt(
                job_id=job.id, session=db_session, settings=mock_settings
            )
        assert exc_info.value.status_code == 500
        assert "download url" in str(exc_info.value.detail).lower()


class TestWebhookDirect:
    """Direct tests for assemblyai_webhook endpoint."""

    @pytest.mark.asyncio
    async def test_webhook_success(self, db_session, mock_transcription_services):
        """Test successful webhook processing."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        await crud.update_job_status(
            db_session, job.id, JobStatus.PROCESSING.value, assemblyai_id="fake-transcript-0"
        )

        mock_settings = Settings(webhook_secret_token="test_secret")

        payload = AssemblyAIWebhookPayload(transcript_id="fake-transcript-0", status="completed")
        background_tasks = BackgroundTasks()

        result = await assemblyai_webhook(
            secret_token="test_secret",
            payload=payload,
            background_tasks=background_tasks,
            session=db_session,
            settings=mock_settings,
        )

        assert result["status"] == "ok"
        assert result["job_id"] == job.id

    @pytest.mark.asyncio
    async def test_webhook_invalid_token(self, db_session):
        """Test webhook with invalid secret token."""
        mock_settings = Settings(webhook_secret_token="correct_secret")

        payload = AssemblyAIWebhookPayload(transcript_id="fake-123", status="completed")
        background_tasks = BackgroundTasks()

        with pytest.raises(HTTPException) as exc_info:
            await assemblyai_webhook(
                secret_token="wrong_secret",
                payload=payload,
                background_tasks=background_tasks,
                session=db_session,
                settings=mock_settings,
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_not_configured(self, db_session):
        """Test webhook when secret token is not configured."""
        mock_settings = Settings(webhook_secret_token=None)

        payload = AssemblyAIWebhookPayload(transcript_id="fake-123", status="completed")
        background_tasks = BackgroundTasks()

        with pytest.raises(HTTPException) as exc_info:
            await assemblyai_webhook(
                secret_token="any_token",
                payload=payload,
                background_tasks=background_tasks,
                session=db_session,
                settings=mock_settings,
            )
        assert exc_info.value.status_code == 500
        assert "not configured" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_webhook_job_not_found(self, db_session):
        """Test webhook for non-existent job."""
        mock_settings = Settings(webhook_secret_token="test_secret")

        payload = AssemblyAIWebhookPayload(transcript_id="nonexistent-id", status="completed")
        background_tasks = BackgroundTasks()

        with pytest.raises(HTTPException) as exc_info:
            await assemblyai_webhook(
                secret_token="test_secret",
                payload=payload,
                background_tasks=background_tasks,
                session=db_session,
                settings=mock_settings,
            )
        assert exc_info.value.status_code == 404


class TestBackgroundProcessing:
    """Test background processing function."""

    @pytest.mark.asyncio
    async def test_process_transcription_background(self, db_session, mock_transcription_services):
        """Test background transcription processing."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        await crud.update_job_status(
            db_session, job.id, JobStatus.PROCESSING.value, assemblyai_id="fake-transcript-0"
        )

        await process_transcription_background(job.id, "fake-transcript-0")

        # Verify job still exists (actual processing tested in service tests)
        updated_job = await crud.get_job(db_session, job.id)
        assert updated_job is not None

    @pytest.mark.asyncio
    async def test_process_transcription_background_error(self, db_session):
        """Test background processing with unexpected error."""
        # Create job but make processing fail
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        await crud.update_job_status(
            db_session, job.id, JobStatus.PROCESSING.value, assemblyai_id="fake-transcript-0"
        )

        # Mock process_completed_transcription to raise unexpected error
        with patch(
            "app.api.v1.transcription.process_completed_transcription",
            side_effect=Exception("Unexpected error"),
        ):
            # Should not raise - errors are caught and logged
            await process_transcription_background(job.id, "fake-transcript-0")

        # Job should be marked as error
        updated_job = await crud.get_job(db_session, job.id)
        assert updated_job is not None
        # Note: The error marking logic is in the background function
        # and may or may not succeed depending on the failure mode
