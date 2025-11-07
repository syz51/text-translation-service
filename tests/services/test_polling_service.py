"""Tests for polling service."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.db.models import JobStatus, TranscriptionJob
from app.services.polling_service import PollingService


@pytest.fixture
def polling_service():
    """Create polling service instance."""
    return PollingService()


@pytest.fixture
def stale_job():
    """Create a stale job fixture."""
    # Job created 3 hours ago (beyond default 2 hour threshold)
    created_at = datetime.now(UTC) - timedelta(hours=3)
    return TranscriptionJob(
        id="stale-job-123",
        audio_s3_key="audio/stale-job-123.mp3",
        status=JobStatus.PROCESSING.value,
        assemblyai_id="assemblyai-123",
        created_at=created_at,
        language_detection=False,
        speaker_labels=False,
    )


@pytest.mark.asyncio
async def test_polling_service_start_stop(polling_service):
    """Test polling service start and stop."""
    # Mock settings to enable polling
    mock_settings = Settings(
        polling_enabled=True,
        polling_interval=300,
        stale_job_threshold=7200,
    )
    with patch("app.services.polling_service.get_settings", return_value=mock_settings):
        await polling_service.start()
        assert polling_service._task is not None
        assert not polling_service._should_stop

        await polling_service.stop()
        assert polling_service._should_stop


@pytest.mark.asyncio
async def test_polling_service_disabled(polling_service):
    """Test polling service respects POLLING_ENABLED=false."""
    mock_settings = Settings(polling_enabled=False)
    with patch("app.services.polling_service.get_settings", return_value=mock_settings):
        await polling_service.start()
        assert polling_service._task is None


@pytest.mark.asyncio
async def test_poll_stale_jobs_no_jobs(polling_service):
    """Test polling when no jobs exist (webhook mode)."""
    mock_settings = Settings(
        webhook_base_url="https://example.com",
        webhook_secret_token="secret",
    )
    with (
        patch("app.services.polling_service.get_settings", return_value=mock_settings),
        patch("app.services.polling_service.crud.get_stale_processing_jobs") as mock_get,
    ):
        mock_get.return_value = []
        await polling_service._poll_stale_jobs()
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_poll_active_jobs_no_jobs(polling_service):
    """Test polling when no jobs exist (active polling mode without webhooks)."""
    mock_settings = Settings(
        webhook_base_url=None,
        webhook_secret_token=None,
    )
    with (
        patch("app.services.polling_service.get_settings", return_value=mock_settings),
        patch("app.services.polling_service.crud.get_all_processing_jobs") as mock_get,
    ):
        mock_get.return_value = []
        await polling_service._poll_stale_jobs()
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_poll_stale_jobs_recovery(polling_service, stale_job):
    """Test polling recovers stale jobs (webhook mode)."""
    mock_process = AsyncMock()
    mock_settings = Settings(
        webhook_base_url="https://example.com",
        webhook_secret_token="secret",
    )

    with (
        patch("app.services.polling_service.get_settings", return_value=mock_settings),
        patch("app.services.polling_service.crud.get_stale_processing_jobs") as mock_get,
        patch(
            "app.services.polling_service.process_completed_transcription", mock_process
        ) as mock_process,
    ):
        mock_get.return_value = [stale_job]

        await polling_service._poll_stale_jobs()

        mock_get.assert_called_once()
        mock_process.assert_called_once()
        # Verify it was called with correct job_id and assemblyai_id
        call_args = mock_process.call_args
        assert call_args[0][1] == stale_job.id  # job_id
        assert call_args[0][2] == stale_job.assemblyai_id  # assemblyai_id


@pytest.mark.asyncio
async def test_poll_active_jobs_recovery(polling_service, stale_job):
    """Test active polling recovers jobs (no webhook mode)."""
    mock_process = AsyncMock()
    mock_settings = Settings(
        webhook_base_url=None,
        webhook_secret_token=None,
    )

    with (
        patch("app.services.polling_service.get_settings", return_value=mock_settings),
        patch("app.services.polling_service.crud.get_all_processing_jobs") as mock_get,
        patch(
            "app.services.polling_service.process_completed_transcription", mock_process
        ) as mock_process,
    ):
        mock_get.return_value = [stale_job]

        await polling_service._poll_stale_jobs()

        mock_get.assert_called_once()
        mock_process.assert_called_once()
        # Verify it was called with correct job_id and assemblyai_id
        call_args = mock_process.call_args
        assert call_args[0][1] == stale_job.id  # job_id
        assert call_args[0][2] == stale_job.assemblyai_id  # assemblyai_id


@pytest.mark.asyncio
async def test_poll_stale_jobs_error_handling(polling_service, stale_job):
    """Test polling handles errors gracefully."""
    mock_process = AsyncMock(side_effect=Exception("Test error"))
    mock_settings = Settings(
        webhook_base_url="https://example.com",
        webhook_secret_token="secret",
    )

    with (
        patch("app.services.polling_service.get_settings", return_value=mock_settings),
        patch("app.services.polling_service.crud.get_stale_processing_jobs") as mock_get,
        patch(
            "app.services.polling_service.process_completed_transcription", mock_process
        ) as mock_process,
    ):
        mock_get.return_value = [stale_job]

        # Should not raise exception
        await polling_service._poll_stale_jobs()

        mock_get.assert_called_once()
        mock_process.assert_called_once()


@pytest.mark.asyncio
async def test_poll_stale_jobs_multiple_jobs(polling_service, stale_job):
    """Test polling processes multiple stale jobs."""
    stale_job2 = TranscriptionJob(
        id="stale-job-456",
        audio_s3_key="audio/stale-job-456.mp3",
        status=JobStatus.PROCESSING.value,
        assemblyai_id="assemblyai-456",
        created_at=datetime.now(UTC) - timedelta(hours=3),
        language_detection=False,
        speaker_labels=False,
    )

    mock_process = AsyncMock()
    mock_settings = Settings(
        webhook_base_url="https://example.com",
        webhook_secret_token="secret",
    )

    with (
        patch("app.services.polling_service.get_settings", return_value=mock_settings),
        patch("app.services.polling_service.crud.get_stale_processing_jobs") as mock_get,
        patch(
            "app.services.polling_service.process_completed_transcription", mock_process
        ) as mock_process,
    ):
        mock_get.return_value = [stale_job, stale_job2]

        await polling_service._poll_stale_jobs()

        mock_get.assert_called_once()
        assert mock_process.call_count == 2


@pytest.mark.asyncio
async def test_polling_loop_integration(polling_service):
    """Test polling loop runs periodically."""
    poll_count = 0

    async def mock_poll():
        nonlocal poll_count
        poll_count += 1

    mock_settings = Settings(
        polling_enabled=True,
        polling_interval=1,  # 1 second interval
        stale_job_threshold=7200,
    )

    with (
        patch("app.services.polling_service.get_settings", return_value=mock_settings),
        patch.object(polling_service, "_poll_stale_jobs", mock_poll),
    ):
        await polling_service.start()

        # Let it run for a few iterations
        await asyncio.sleep(2.5)

        await polling_service.stop()

        # Should have polled at least 2 times
        assert poll_count >= 2


@pytest.mark.asyncio
async def test_idempotency_check(polling_service, stale_job):
    """Test that process_completed_transcription is idempotent."""
    # Simulate job already completed
    completed_job = TranscriptionJob(
        id="completed-job-789",
        audio_s3_key="audio/completed-job-789.mp3",
        status=JobStatus.COMPLETED.value,
        assemblyai_id="assemblyai-789",
        srt_s3_key="srt/completed-job-789.srt",
        created_at=datetime.now(UTC) - timedelta(hours=3),
        completed_at=datetime.now(UTC) - timedelta(hours=2),
        language_detection=False,
        speaker_labels=False,
    )

    from app.services.transcription_service import process_completed_transcription

    mock_assemblyai = AsyncMock()

    with (
        patch("app.services.transcription_service.crud.get_job") as mock_get,
        patch("app.services.transcription_service.assemblyai_client", mock_assemblyai),
    ):
        mock_get.return_value = completed_job

        from app.db.base import SessionLocal

        async with SessionLocal() as session:
            # Should return early without calling AssemblyAI
            assert completed_job.assemblyai_id is not None
            await process_completed_transcription(
                session, completed_job.id, completed_job.assemblyai_id
            )

        # AssemblyAI client should NOT be called
        mock_assemblyai.fetch_transcript.assert_not_called()
