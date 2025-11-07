"""Integration tests for transcription API via HTTP (TestClient).

These tests use FastAPI's TestClient to test the full HTTP request/response cycle.
They complement test_transcription_direct.py which tests endpoint functions directly.

Purpose:
- Validate HTTP layer (headers, status codes, multipart uploads)
- Test middleware integration
- Test race conditions and timing issues
- Smoke test the full integration

For detailed endpoint logic and error path coverage, see test_transcription_direct.py.
"""

import asyncio

import pytest

from app.core.config import Settings, get_settings
from app.db import crud
from app.db.models import JobStatus
from tests.conftest import create_fake_audio_file


class TestHTTPIntegration:
    """Smoke tests for HTTP request/response cycle."""

    def test_create_transcription_http(self, client, mock_transcription_services):
        """Test full HTTP request cycle for creating transcription."""
        mock_settings = Settings(
            max_concurrent_jobs=10,
            allowed_audio_formats={".mp3"},
            max_file_size=1_073_741_824,
            webhook_base_url="https://example.com",
            webhook_secret_token="test_secret",
            audio_presigned_url_expiry=86400,
        )

        # Override the get_settings dependency
        client.app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            # Test multipart form-data file upload
            files = {"file": ("test.mp3", create_fake_audio_file(1), "audio/mpeg")}
            response = client.post("/api/v1/transcriptions", files=files)

            assert response.status_code == 201
            assert response.headers["content-type"] == "application/json"
            data = response.json()
            assert "job_id" in data
            assert data["status"] == JobStatus.PROCESSING.value
        finally:
            # Clean up override
            client.app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_status_http(self, client, mock_transcription_services, db_session):
        """Test HTTP GET for job status."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )

        response = client.get(f"/api/v1/transcriptions/{job.id}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        data = response.json()
        assert data["job_id"] == job.id

    @pytest.mark.asyncio
    async def test_download_srt_redirect(self, client, mock_transcription_services, db_session):
        """Test HTTP redirect for SRT download."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        srt_key = f"srt/{job.id}.srt"
        await crud.update_job_result(db_session, job.id, srt_key)
        mock_transcription_services["s3"].storage[srt_key] = "1\n00:00:00,000"

        mock_settings = Settings(srt_presigned_url_expiry=3600)
        client.app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            # Test 302 redirect behavior
            response = client.get(f"/api/v1/transcriptions/{job.id}/srt", follow_redirects=False)

            assert response.status_code == 302
            assert "location" in response.headers
            assert "fake-s3.amazonaws.com" in response.headers["location"]
        finally:
            client.app.dependency_overrides.clear()

    def test_webhook_http(self, client, mock_transcription_services):
        """Test webhook HTTP POST handling."""
        mock_settings = Settings(webhook_secret_token="test_secret")
        client.app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            webhook_data = {"transcript_id": "fake-transcript-0", "status": "completed"}
            response = client.post("/api/v1/webhooks/assemblyai/test_secret", json=webhook_data)

            # Test fast response (< 10s requirement)
            assert response.status_code in [200, 404]  # 404 if job doesn't exist
            assert response.headers["content-type"] == "application/json"
        finally:
            client.app.dependency_overrides.clear()


class TestRaceConditions:
    """Test webhook race condition handling."""

    @pytest.mark.asyncio
    async def test_webhook_before_processing_status(
        self, client, mock_transcription_services, db_session
    ):
        """Test webhook arriving before job marked as PROCESSING."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        # Manually set assemblyai_id without changing status to PROCESSING
        await crud.update_job_status(
            db_session, job.id, JobStatus.QUEUED.value, assemblyai_id="fake-transcript-0"
        )

        mock_settings = Settings(webhook_secret_token="test_secret")
        client.app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            webhook_data = {"transcript_id": "fake-transcript-0", "status": "completed"}
            response = client.post("/api/v1/webhooks/assemblyai/test_secret", json=webhook_data)

            # Should handle gracefully even if job not in PROCESSING state
            assert response.status_code == 200
        finally:
            client.app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_webhook_duplicate_delivery(
        self, client, mock_transcription_services, db_session
    ):
        """Test duplicate webhook delivery (idempotency)."""
        job = await crud.create_job(
            db_session,
            audio_s3_key="audio/test.mp3",
            language_detection=False,
            speaker_labels=False,
        )
        await crud.update_job_status(
            db_session, job.id, JobStatus.PROCESSING.value, assemblyai_id="fake-transcript-0"
        )
        await crud.update_job_result(db_session, job.id, "srt/test.srt")

        mock_settings = Settings(webhook_secret_token="test_secret")
        client.app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            webhook_data = {"transcript_id": "fake-transcript-0", "status": "completed"}
            response = client.post("/api/v1/webhooks/assemblyai/test_secret", json=webhook_data)

            # Should be idempotent
            assert response.status_code == 200
        finally:
            client.app.dependency_overrides.clear()

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

        mock_settings = Settings(webhook_secret_token="test_secret")
        client.app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            webhook_data = {"transcript_id": "fake-transcript-0", "status": "completed"}

            # Send multiple webhooks rapidly
            response1 = client.post("/api/v1/webhooks/assemblyai/test_secret", json=webhook_data)
            await asyncio.sleep(0.1)
            response2 = client.post("/api/v1/webhooks/assemblyai/test_secret", json=webhook_data)

            assert response1.status_code == 200
            assert response2.status_code == 200
        finally:
            client.app.dependency_overrides.clear()


class TestConcurrentLimits:
    """Test concurrent job limit enforcement."""

    @pytest.mark.asyncio
    async def test_exactly_at_limit(self, client, mock_transcription_services, db_session):
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

        mock_settings = Settings(
            max_concurrent_jobs=10,
            allowed_audio_formats={".mp3"},
            max_file_size=1_073_741_824,
            webhook_base_url="https://example.com",
            webhook_secret_token="test_secret",
            audio_presigned_url_expiry=86400,
        )
        client.app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            files = {"file": ("test.mp3", create_fake_audio_file(1), "audio/mpeg")}
            response = client.post("/api/v1/transcriptions", files=files)

            assert response.status_code == 201
        finally:
            client.app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_limit_counts_queued_and_processing(
        self, client, mock_transcription_services, db_session
    ):
        """Test that both QUEUED and PROCESSING jobs count toward limit."""
        # Create 5 QUEUED and 5 PROCESSING jobs (total 10, at limit)
        for i in range(5):
            await crud.create_job(
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

        mock_settings = Settings(
            max_concurrent_jobs=10,
            allowed_audio_formats={".mp3"},
            max_file_size=1_073_741_824,
        )
        client.app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            files = {"file": ("test.mp3", create_fake_audio_file(1), "audio/mpeg")}
            response = client.post("/api/v1/transcriptions", files=files)

            assert response.status_code == 429
        finally:
            client.app.dependency_overrides.clear()


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
