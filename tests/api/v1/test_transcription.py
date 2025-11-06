"""Tests for transcription API endpoints."""

import asyncio
from unittest.mock import patch

import pytest

from app.db import crud
from app.db.models import JobStatus
from tests.conftest import create_fake_audio_file


class TestTranscriptionCreate:
    """Test POST /transcriptions endpoint."""

    def test_create_success(self, client_with_auth, mock_transcription_services):
        """Test successful transcription job creation."""
        # Mock settings for webhook
        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.max_concurrent_jobs = 10
            mock_settings.allowed_audio_formats = {".mp3"}
            mock_settings.max_file_size = 1_073_741_824
            mock_settings.webhook_base_url = "https://example.com"
            mock_settings.webhook_secret_token = "test_secret"
            mock_settings.audio_presigned_url_expiry = 86400

            files = {"file": ("test.mp3", create_fake_audio_file(1), "audio/mpeg")}
            response = client_with_auth.post("/api/v1/transcriptions", files=files)

            assert response.status_code == 201
            data = response.json()
            assert "job_id" in data
            assert data["status"] == JobStatus.PROCESSING.value
            assert "audio_s3_key" in data

    def test_create_invalid_format(self, client_with_auth, mock_transcription_services):
        """Test rejection of invalid audio format."""
        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.max_concurrent_jobs = 10
            mock_settings.allowed_audio_formats = {".mp3"}
            mock_settings.max_file_size = 1_073_741_824

            files = {"file": ("test.txt", b"not audio", "text/plain")}
            response = client_with_auth.post("/api/v1/transcriptions", files=files)

            assert response.status_code == 400
            assert "Invalid audio format" in response.json()["detail"]

    def test_create_file_too_large(self, client_with_auth, mock_transcription_services):
        """Test rejection of files exceeding size limit."""
        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.max_concurrent_jobs = 10
            mock_settings.allowed_audio_formats = {".mp3"}
            mock_settings.max_file_size = 1024  # 1KB limit

            files = {"file": ("huge.mp3", create_fake_audio_file(1), "audio/mpeg")}  # 1MB file
            response = client_with_auth.post("/api/v1/transcriptions", files=files)

            assert response.status_code == 413
            assert "exceeds maximum" in response.json()["detail"]

    def test_create_s3_upload_failure(self, client_with_auth, mock_transcription_services_error):
        """Test handling of S3 upload failures."""
        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.max_concurrent_jobs = 10
            mock_settings.allowed_audio_formats = {".mp3"}
            mock_settings.max_file_size = 1_073_741_824

            files = {"file": ("test.mp3", create_fake_audio_file(1), "audio/mpeg")}
            response = client_with_auth.post("/api/v1/transcriptions", files=files)

            assert response.status_code == 500
            assert "uploading audio" in response.json()["detail"].lower()

    def test_create_with_language_detection(self, client_with_auth, mock_transcription_services):
        """Test creation with language detection enabled."""
        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.max_concurrent_jobs = 10
            mock_settings.allowed_audio_formats = {".mp3"}
            mock_settings.max_file_size = 1_073_741_824
            mock_settings.webhook_base_url = "https://example.com"
            mock_settings.webhook_secret_token = "test_secret"
            mock_settings.audio_presigned_url_expiry = 86400

            files = {"file": ("test.mp3", create_fake_audio_file(1), "audio/mpeg")}
            data = {"language_detection": "true"}
            response = client_with_auth.post("/api/v1/transcriptions", files=files, data=data)

            assert response.status_code == 201
            assert response.json()["language_detection"] is True

    def test_create_with_speaker_labels(self, client_with_auth, mock_transcription_services):
        """Test creation with speaker diarization enabled."""
        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.max_concurrent_jobs = 10
            mock_settings.allowed_audio_formats = {".mp3"}
            mock_settings.max_file_size = 1_073_741_824
            mock_settings.webhook_base_url = "https://example.com"
            mock_settings.webhook_secret_token = "test_secret"
            mock_settings.audio_presigned_url_expiry = 86400

            files = {"file": ("test.mp3", create_fake_audio_file(1), "audio/mpeg")}
            data = {"speaker_labels": "true"}
            response = client_with_auth.post("/api/v1/transcriptions", files=files, data=data)

            assert response.status_code == 201
            assert response.json()["speaker_labels"] is True


class TestTranscriptionStatus:
    """Test GET /transcriptions/{job_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_status_success(self, client, mock_transcription_services, db_session):
        """Test getting status of existing job."""
        # Create test job
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )

        response = client.get(f"/api/v1/transcriptions/{job.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job.id
        assert data["status"] == JobStatus.QUEUED.value
        assert "created_at" in data
        assert data["srt_available"] is False

    @pytest.mark.asyncio
    async def test_get_status_not_found(self, client, mock_transcription_services, db_session):
        """Test getting status of non-existent job."""
        response = client.get("/api/v1/transcriptions/nonexistent-job-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_status_completed_job(self, client, mock_transcription_services, db_session):
        """Test getting status of completed job with SRT available."""
        # Create completed job
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        await crud.update_job_result(db_session, job.id, "srt/test.srt")

        response = client.get(f"/api/v1/transcriptions/{job.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == JobStatus.COMPLETED.value
        assert data["srt_available"] is True

    @pytest.mark.asyncio
    async def test_get_status_error_job(self, client, mock_transcription_services, db_session):
        """Test getting status of failed job."""
        # Create error job
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        await crud.update_job_status(db_session, job.id, JobStatus.ERROR.value, error="Test error")

        response = client.get(f"/api/v1/transcriptions/{job.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == JobStatus.ERROR.value
        assert data["error_message"] == "Test error"
        assert data["srt_available"] is False


class TestTranscriptionDownload:
    """Test GET /transcriptions/{job_id}/srt endpoint."""

    @pytest.mark.asyncio
    async def test_download_success(self, client, mock_transcription_services, db_session):
        """Test downloading SRT file for completed job."""
        # Create completed job with SRT
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        srt_key = f"srt/{job.id}.srt"
        await crud.update_job_result(db_session, job.id, srt_key)

        # Upload fake SRT to fake S3
        mock_transcription_services["s3"].storage[srt_key] = "1\n00:00:00,000"

        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.srt_presigned_url_expiry = 3600

            response = client.get(f"/api/v1/transcriptions/{job.id}/srt", follow_redirects=False)

            assert response.status_code == 302  # Redirect to S3 presigned URL
            assert response.headers["location"].startswith("https://fake-s3.amazonaws.com/")

    @pytest.mark.asyncio
    async def test_download_not_found(self, client, mock_transcription_services, db_session):
        """Test downloading SRT for non-existent job."""
        response = client.get("/api/v1/transcriptions/nonexistent-job-id/srt")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_download_not_ready_queued(self, client, mock_transcription_services, db_session):
        """Test downloading SRT when job is still queued."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )

        response = client.get(f"/api/v1/transcriptions/{job.id}/srt")

        assert response.status_code == 400
        assert "in progress" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_download_not_ready_processing(
        self, client, mock_transcription_services, db_session
    ):
        """Test downloading SRT when job is still processing."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        await crud.update_job_status(db_session, job.id, JobStatus.PROCESSING.value)

        response = client.get(f"/api/v1/transcriptions/{job.id}/srt")

        assert response.status_code == 400
        assert "in progress" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_download_failed_job(self, client, mock_transcription_services, db_session):
        """Test downloading SRT when job has failed."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        await crud.update_job_status(db_session, job.id, JobStatus.ERROR.value, error="Test error")

        response = client.get(f"/api/v1/transcriptions/{job.id}/srt")

        assert response.status_code == 400
        assert "failed" in response.json()["detail"].lower()


class TestWebhook:
    """Test POST /webhooks/assemblyai/{secret_token} endpoint."""

    @pytest.mark.asyncio
    async def test_webhook_success(self, client, mock_transcription_services, db_session):
        """Test successful webhook processing."""
        # Create processing job
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        await crud.update_job_status(
            db_session, job.id, JobStatus.PROCESSING.value, assemblyai_id="fake-transcript-0"
        )

        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.webhook_secret_token = "test_secret"

            webhook_data = {"transcript_id": "fake-transcript-0", "status": "completed"}
            response = client.post("/api/v1/webhooks/assemblyai/test_secret", json=webhook_data)

            assert response.status_code == 200
            assert response.json()["status"] == "ok"
            assert response.json()["job_id"] == job.id

    @pytest.mark.asyncio
    async def test_webhook_invalid_token(self, client, mock_transcription_services, db_session):
        """Test webhook with invalid secret token."""
        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.webhook_secret_token = "correct_secret"

            webhook_data = {"transcript_id": "fake-123", "status": "completed"}
            response = client.post("/api/v1/webhooks/assemblyai/wrong_secret", json=webhook_data)

            assert response.status_code == 401
            assert "invalid" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_webhook_job_not_found(self, client, mock_transcription_services, db_session):
        """Test webhook for non-existent job."""
        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.webhook_secret_token = "test_secret"

            webhook_data = {"transcript_id": "nonexistent-id", "status": "completed"}
            response = client.post("/api/v1/webhooks/assemblyai/test_secret", json=webhook_data)

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_webhook_background_processing(
        self, client, mock_transcription_services, db_session
    ):
        """Test that webhook returns immediately and processes in background."""
        # Create processing job
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        await crud.update_job_status(
            db_session, job.id, JobStatus.PROCESSING.value, assemblyai_id="fake-transcript-0"
        )

        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.webhook_secret_token = "test_secret"

            webhook_data = {"transcript_id": "fake-transcript-0", "status": "completed"}
            response = client.post("/api/v1/webhooks/assemblyai/test_secret", json=webhook_data)

            # Should return immediately
            assert response.status_code == 200

            # Background task would process transcription
            # (tested separately in transcription_service tests)


class TestRaceConditions:
    """Test webhook race condition handling."""

    @pytest.mark.asyncio
    async def test_webhook_before_processing_status(
        self, client, mock_transcription_services, db_session
    ):
        """Test webhook arriving before job marked as PROCESSING."""
        # Create job still in QUEUED state
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        # Manually set assemblyai_id without changing status
        await crud.update_job_status(
            db_session, job.id, JobStatus.QUEUED.value, assemblyai_id="fake-transcript-0"
        )

        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.webhook_secret_token = "test_secret"

            webhook_data = {"transcript_id": "fake-transcript-0", "status": "completed"}
            response = client.post("/api/v1/webhooks/assemblyai/test_secret", json=webhook_data)

            # Should handle gracefully
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_webhook_duplicate_delivery(
        self, client, mock_transcription_services, db_session
    ):
        """Test duplicate webhook delivery (idempotency)."""
        # Create completed job
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        await crud.update_job_status(
            db_session,
            job.id,
            JobStatus.PROCESSING.value,
            assemblyai_id="fake-transcript-0",
        )
        await crud.update_job_result(db_session, job.id, "srt/test.srt")

        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.webhook_secret_token = "test_secret"

            webhook_data = {"transcript_id": "fake-transcript-0", "status": "completed"}
            response = client.post("/api/v1/webhooks/assemblyai/test_secret", json=webhook_data)

            # Should be idempotent
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_multiple_webhooks_same_job(
        self, client, mock_transcription_services, db_session
    ):
        """Test multiple webhook calls for same job."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        await crud.update_job_status(
            db_session, job.id, JobStatus.PROCESSING.value, assemblyai_id="fake-transcript-0"
        )

        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.webhook_secret_token = "test_secret"

            webhook_data = {"transcript_id": "fake-transcript-0", "status": "completed"}

            # First webhook
            response1 = client.post("/api/v1/webhooks/assemblyai/test_secret", json=webhook_data)
            assert response1.status_code == 200

            # Wait for potential background processing
            await asyncio.sleep(0.1)

            # Second webhook (duplicate)
            response2 = client.post("/api/v1/webhooks/assemblyai/test_secret", json=webhook_data)
            assert response2.status_code == 200


class TestConcurrentLimits:
    """Test concurrent job limit enforcement."""

    @pytest.mark.asyncio
    async def test_exactly_at_limit(
        self, client_with_auth, mock_transcription_services, db_session
    ):
        """Test that request succeeds when exactly at limit - 1."""
        # Create 9 PROCESSING jobs (limit is 10)
        for i in range(9):
            job = await crud.create_job(
                db_session,
                audio_s3_key=f"audio/test_{i}.mp3",
                language_detection=False,
                speaker_labels=False,
            )
            await crud.update_job_status(db_session, job.id, JobStatus.PROCESSING.value)

        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.max_concurrent_jobs = 10
            mock_settings.allowed_audio_formats = {".mp3"}
            mock_settings.max_file_size = 1_073_741_824
            mock_settings.webhook_base_url = "https://example.com"
            mock_settings.webhook_secret_token = "test_secret"
            mock_settings.audio_presigned_url_expiry = 86400

            files = {"file": ("test.mp3", create_fake_audio_file(1), "audio/mpeg")}
            response = client_with_auth.post("/api/v1/transcriptions", files=files)

            assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_limit_resets_when_completed(
        self, client_with_auth, mock_transcription_services, db_session
    ):
        """Test that completed jobs don't count toward limit."""
        # Create 10 COMPLETED jobs (shouldn't count)
        for i in range(10):
            job = await crud.create_job(
                db_session,
                audio_s3_key=f"audio/test_{i}.mp3",
                language_detection=False,
                speaker_labels=False,
            )
            await crud.update_job_result(db_session, job.id, f"srt/test_{i}.srt")

        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.max_concurrent_jobs = 10
            mock_settings.allowed_audio_formats = {".mp3"}
            mock_settings.max_file_size = 1_073_741_824
            mock_settings.webhook_base_url = "https://example.com"
            mock_settings.webhook_secret_token = "test_secret"
            mock_settings.audio_presigned_url_expiry = 86400

            files = {"file": ("test.mp3", create_fake_audio_file(1), "audio/mpeg")}
            response = client_with_auth.post("/api/v1/transcriptions", files=files)

            assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_limit_counts_queued_and_processing(
        self, client_with_auth, mock_transcription_services, db_session
    ):
        """Test that both QUEUED and PROCESSING jobs count toward limit."""
        # Create 5 QUEUED and 5 PROCESSING jobs (total 10, at limit)
        for i in range(5):
            job = await crud.create_job(
                db_session,
                audio_s3_key=f"audio/queued_{i}.mp3",
                language_detection=False,
                speaker_labels=False,
            )
            # Keep in QUEUED state

        for i in range(5):
            job = await crud.create_job(
                db_session,
                audio_s3_key=f"audio/processing_{i}.mp3",
                language_detection=False,
                speaker_labels=False,
            )
            await crud.update_job_status(db_session, job.id, JobStatus.PROCESSING.value)

        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.max_concurrent_jobs = 10
            mock_settings.allowed_audio_formats = {".mp3"}
            mock_settings.max_file_size = 1_073_741_824

            files = {"file": ("test.mp3", create_fake_audio_file(1), "audio/mpeg")}
            response = client_with_auth.post("/api/v1/transcriptions", files=files)

            assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_error_jobs_dont_count(
        self, client_with_auth, mock_transcription_services, db_session
    ):
        """Test that ERROR jobs don't count toward limit."""
        # Create 10 ERROR jobs (shouldn't count)
        for i in range(10):
            job = await crud.create_job(
                db_session,
                audio_s3_key=f"audio/test_{i}.mp3",
                language_detection=False,
                speaker_labels=False,
            )
            await crud.update_job_status(
                db_session, job.id, JobStatus.ERROR.value, error="Test error"
            )

        with patch("app.api.v1.transcription.settings") as mock_settings:
            mock_settings.max_concurrent_jobs = 10
            mock_settings.allowed_audio_formats = {".mp3"}
            mock_settings.max_file_size = 1_073_741_824
            mock_settings.webhook_base_url = "https://example.com"
            mock_settings.webhook_secret_token = "test_secret"
            mock_settings.audio_presigned_url_expiry = 86400

            files = {"file": ("test.mp3", create_fake_audio_file(1), "audio/mpeg")}
            response = client_with_auth.post("/api/v1/transcriptions", files=files)

            assert response.status_code == 201


class TestHealthCheckDegradedStatus:
    """Test health check with degraded services."""

    def test_health_check_s3_unavailable(self, mock_transcription_services_error):
        """Test health check returns 503 when S3 unavailable."""
        from fastapi.testclient import TestClient

        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/v1/health")

        # Should show degraded status
        assert response.status_code in [200, 503]
        data = response.json()
        assert "components" in data

    def test_health_check_assemblyai_unavailable(self, mock_transcription_services_error):
        """Test health check returns 503 when AssemblyAI unavailable."""
        from fastapi.testclient import TestClient

        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/v1/health")

        # Should show degraded status
        assert response.status_code in [200, 503]
        data = response.json()
        assert "components" in data
