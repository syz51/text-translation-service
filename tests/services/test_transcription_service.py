"""Unit tests for transcription service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.db.models import JobStatus
from app.services.transcription_service import get_backoff_delay, process_completed_transcription


class TestGetBackoffDelay:
    """Test get_backoff_delay utility function."""

    def test_first_retry(self):
        """Test backoff delay for first retry."""
        result = get_backoff_delay(1, [1, 2, 4, 8])
        assert result == 1

    def test_second_retry(self):
        """Test backoff delay for second retry."""
        result = get_backoff_delay(2, [1, 2, 4, 8])
        assert result == 2

    def test_third_retry(self):
        """Test backoff delay for third retry."""
        result = get_backoff_delay(3, [1, 2, 4, 8])
        assert result == 4

    def test_last_retry(self):
        """Test backoff delay for last retry."""
        result = get_backoff_delay(4, [1, 2, 4, 8])
        assert result == 8

    def test_retry_exceeds_list_length(self):
        """Test that delay caps at last value when retry exceeds list."""
        result = get_backoff_delay(10, [1, 2, 4])
        assert result == 4

    def test_single_delay_value(self):
        """Test with single delay value."""
        result = get_backoff_delay(1, [5])
        assert result == 5
        result = get_backoff_delay(10, [5])
        assert result == 5


def create_mock_job(retry_count=0):
    """Helper to create mock job."""
    mock_job = MagicMock()
    mock_job.id = "test-job-id"
    mock_job.retry_count = retry_count
    return mock_job


class TestProcessCompletedTranscription:
    """Test process_completed_transcription function."""

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    @patch("app.services.transcription_service.s3_storage")
    async def test_success_flow(self, mock_s3, mock_aai, mock_crud, mock_get_settings):
        """Test successful transcription processing."""
        mock_settings = Settings(retry_max_attempts=3, retry_backoff=[1, 2, 4])
        mock_get_settings.return_value = mock_settings

        mock_crud.get_job = AsyncMock(return_value=create_mock_job())

        mock_transcript_obj = MagicMock()
        mock_aai.fetch_transcript = AsyncMock(
            return_value={
                "status": "completed",
                "text": "Test transcript",
                "transcript_obj": mock_transcript_obj,
            }
        )
        mock_aai.convert_to_srt = AsyncMock(return_value="1\n00:00:00,000 --> 00:00:01,000\nTest")
        mock_s3.upload_srt = AsyncMock(return_value="srt/test-job-id.srt")
        mock_crud.update_job_result = AsyncMock()

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        mock_aai.fetch_transcript.assert_called_once_with("aai-123")
        mock_aai.convert_to_srt.assert_called_once_with(transcript_obj=mock_transcript_obj)
        mock_s3.upload_srt.assert_called_once()
        mock_crud.update_job_result.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    async def test_job_not_found(self, mock_crud, mock_get_settings):
        """Test handling when job not found."""
        mock_settings = Settings(retry_max_attempts=3)
        mock_get_settings.return_value = mock_settings
        mock_crud.get_job = AsyncMock(return_value=None)

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "nonexistent", "aai-123")

        mock_crud.get_job.assert_called_once_with(mock_session, "nonexistent")

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    async def test_transcript_error_status(self, mock_aai, mock_crud, mock_get_settings):
        """Test handling when transcript has error status."""
        mock_settings = Settings(retry_max_attempts=3)
        mock_get_settings.return_value = mock_settings

        mock_crud.get_job = AsyncMock(return_value=create_mock_job())
        mock_aai.fetch_transcript = AsyncMock(
            return_value={"status": "error", "error": "Transcription failed", "text": None}
        )
        mock_crud.update_job_status = AsyncMock()

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        mock_crud.update_job_status.assert_called_with(
            mock_session, "test-job-id", JobStatus.ERROR.value, error="Transcription failed"
        )

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    async def test_transcript_error_no_message(self, mock_aai, mock_crud, mock_get_settings):
        """Test handling when transcript has error status but no error message."""
        mock_settings = Settings(retry_max_attempts=3)
        mock_get_settings.return_value = mock_settings

        mock_crud.get_job = AsyncMock(return_value=create_mock_job())
        mock_aai.fetch_transcript = AsyncMock(
            return_value={"status": "error", "error": None, "text": None}
        )
        mock_crud.update_job_status = AsyncMock()

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        mock_crud.update_job_status.assert_called_with(
            mock_session,
            "test-job-id",
            JobStatus.ERROR.value,
            error="Unknown AssemblyAI error",
        )

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    @patch("app.services.transcription_service.s3_storage")
    @patch("app.services.transcription_service.asyncio.sleep", new_callable=AsyncMock)
    async def test_transcript_processing_retry_then_success(
        self, mock_sleep, mock_s3, mock_aai, mock_crud, mock_get_settings
    ):
        """Test retry when transcript still processing, then succeeds."""
        mock_settings = Settings(retry_max_attempts=3, retry_backoff=[1, 2, 4])
        mock_get_settings.return_value = mock_settings

        mock_job = create_mock_job()
        mock_crud.get_job = AsyncMock(return_value=mock_job)
        mock_crud.increment_retry = AsyncMock(side_effect=[1, 1])

        mock_transcript_obj = MagicMock()
        mock_aai.fetch_transcript = AsyncMock(
            side_effect=[
                {"status": "processing", "text": None},
                {
                    "status": "completed",
                    "text": "Test",
                    "transcript_obj": mock_transcript_obj,
                },
            ]
        )
        mock_aai.convert_to_srt = AsyncMock(return_value="1\n00:00:00,000\nTest")
        mock_s3.upload_srt = AsyncMock(return_value="srt/test.srt")
        mock_crud.update_job_result = AsyncMock()

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        assert mock_aai.fetch_transcript.call_count == 2
        mock_sleep.assert_called_once_with(1)
        mock_crud.update_job_result.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    @patch("app.services.transcription_service.asyncio.sleep", new_callable=AsyncMock)
    async def test_transcript_processing_max_retries(
        self, mock_sleep, mock_aai, mock_crud, mock_get_settings
    ):
        """Test max retries reached when transcript still processing."""
        mock_settings = Settings(retry_max_attempts=2, retry_backoff=[1, 2])
        mock_get_settings.return_value = mock_settings

        mock_job = create_mock_job()
        mock_crud.get_job = AsyncMock(return_value=mock_job)
        mock_crud.increment_retry = AsyncMock(side_effect=[1, 2])

        mock_aai.fetch_transcript = AsyncMock(return_value={"status": "processing", "text": None})
        mock_crud.update_job_status = AsyncMock()

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        assert mock_aai.fetch_transcript.call_count == 2
        assert mock_sleep.call_count == 1
        mock_crud.update_job_status.assert_called()
        call_args = mock_crud.update_job_status.call_args[1]
        assert "not completed after" in call_args["error"]

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    @patch("app.services.transcription_service.asyncio.sleep", new_callable=AsyncMock)
    async def test_transcript_queued_retry_then_success(
        self, mock_sleep, mock_aai, mock_crud, mock_get_settings
    ):
        """Test retry when transcript in queued state, then succeeds."""
        mock_settings = Settings(retry_max_attempts=3, retry_backoff=[1, 2, 4])
        mock_get_settings.return_value = mock_settings

        mock_job = create_mock_job()
        mock_crud.get_job = AsyncMock(return_value=mock_job)
        mock_crud.increment_retry = AsyncMock(side_effect=[1, 1])

        mock_transcript_obj = MagicMock()
        mock_aai.fetch_transcript = AsyncMock(
            side_effect=[
                {"status": "queued", "text": None},
                {
                    "status": "completed",
                    "text": "Test",
                    "transcript_obj": mock_transcript_obj,
                },
            ]
        )
        mock_aai.convert_to_srt = AsyncMock(return_value="1\n00:00:00,000\nTest")

        mock_s3_storage = AsyncMock()
        mock_s3_storage.upload_srt = AsyncMock(return_value="srt/test.srt")
        mock_crud.update_job_result = AsyncMock()

        mock_session = AsyncMock()

        with patch("app.services.transcription_service.s3_storage", mock_s3_storage):
            await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        assert mock_aai.fetch_transcript.call_count == 2
        mock_sleep.assert_called_once_with(1)

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    async def test_unexpected_transcript_status(self, mock_aai, mock_crud, mock_get_settings):
        """Test handling of unexpected transcript status."""
        mock_settings = Settings(retry_max_attempts=3)
        mock_get_settings.return_value = mock_settings

        mock_crud.get_job = AsyncMock(return_value=create_mock_job())
        mock_aai.fetch_transcript = AsyncMock(
            return_value={"status": "unknown_status", "text": None}
        )
        mock_crud.update_job_status = AsyncMock()

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        mock_crud.update_job_status.assert_called_with(
            mock_session,
            "test-job-id",
            JobStatus.ERROR.value,
            error="Unexpected transcript status: unknown_status",
        )

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    async def test_empty_srt_content(self, mock_aai, mock_crud, mock_get_settings):
        """Test handling when SRT content is empty."""
        mock_settings = Settings(retry_max_attempts=3)
        mock_get_settings.return_value = mock_settings

        mock_crud.get_job = AsyncMock(return_value=create_mock_job())
        mock_transcript_obj = MagicMock()
        mock_aai.fetch_transcript = AsyncMock(
            return_value={
                "status": "completed",
                "text": "Test",
                "transcript_obj": mock_transcript_obj,
            }
        )
        mock_aai.convert_to_srt = AsyncMock(return_value="")
        mock_crud.update_job_status = AsyncMock()

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        mock_crud.update_job_status.assert_called_with(
            mock_session,
            "test-job-id",
            JobStatus.ERROR.value,
            error="Generated SRT content is empty",
        )

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    async def test_whitespace_only_srt(self, mock_aai, mock_crud, mock_get_settings):
        """Test handling when SRT content is whitespace only."""
        mock_settings = Settings(retry_max_attempts=3)
        mock_get_settings.return_value = mock_settings

        mock_crud.get_job = AsyncMock(return_value=create_mock_job())
        mock_transcript_obj = MagicMock()
        mock_aai.fetch_transcript = AsyncMock(
            return_value={
                "status": "completed",
                "text": "Test",
                "transcript_obj": mock_transcript_obj,
            }
        )
        mock_aai.convert_to_srt = AsyncMock(return_value="   \n\n  ")
        mock_crud.update_job_status = AsyncMock()

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        mock_crud.update_job_status.assert_called_with(
            mock_session,
            "test-job-id",
            JobStatus.ERROR.value,
            error="Generated SRT content is empty",
        )

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    @patch("app.services.transcription_service.s3_storage")
    @patch("app.services.transcription_service.asyncio.sleep", new_callable=AsyncMock)
    async def test_exception_retry_then_success(
        self, mock_sleep, mock_s3, mock_aai, mock_crud, mock_get_settings
    ):
        """Test exception triggers retry, then succeeds."""
        mock_settings = Settings(retry_max_attempts=3, retry_backoff=[1, 2, 4])
        mock_get_settings.return_value = mock_settings

        mock_job = create_mock_job()
        mock_crud.get_job = AsyncMock(return_value=mock_job)
        mock_crud.increment_retry = AsyncMock(side_effect=[1, 1])

        mock_transcript_obj = MagicMock()
        mock_aai.fetch_transcript = AsyncMock(
            side_effect=[
                RuntimeError("Network error"),
                {
                    "status": "completed",
                    "text": "Test",
                    "transcript_obj": mock_transcript_obj,
                },
            ]
        )
        mock_aai.convert_to_srt = AsyncMock(return_value="1\n00:00:00,000\nTest")
        mock_s3.upload_srt = AsyncMock(return_value="srt/test.srt")
        mock_crud.update_job_result = AsyncMock()

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        assert mock_aai.fetch_transcript.call_count == 2
        mock_sleep.assert_called_once_with(1)
        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    @patch("app.services.transcription_service.asyncio.sleep", new_callable=AsyncMock)
    async def test_exception_max_retries_reached(
        self, mock_sleep, mock_aai, mock_crud, mock_get_settings
    ):
        """Test max retries reached after repeated exceptions."""
        mock_settings = Settings(retry_max_attempts=2, retry_backoff=[1, 2])
        mock_get_settings.return_value = mock_settings

        mock_job = create_mock_job()
        mock_crud.get_job = AsyncMock(return_value=mock_job)
        mock_crud.increment_retry = AsyncMock(side_effect=[1, 2])

        mock_aai.fetch_transcript = AsyncMock(side_effect=RuntimeError("Network error"))
        mock_crud.update_job_status = AsyncMock()

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        assert mock_aai.fetch_transcript.call_count == 2
        mock_crud.update_job_status.assert_called()
        call_args = mock_crud.update_job_status.call_args
        assert call_args[0][2] == JobStatus.ERROR.value
        assert "Failed after 2 attempts" in call_args[1]["error"]

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    @patch("app.services.transcription_service.s3_storage")
    @patch("app.services.transcription_service.asyncio.sleep", new_callable=AsyncMock)
    async def test_s3_upload_failure_with_retry(
        self, mock_sleep, mock_s3, mock_aai, mock_crud, mock_get_settings
    ):
        """Test S3 upload failure triggers retry."""
        mock_settings = Settings(retry_max_attempts=2, retry_backoff=[1, 2])
        mock_get_settings.return_value = mock_settings

        mock_job = create_mock_job()
        mock_crud.get_job = AsyncMock(return_value=mock_job)
        mock_crud.increment_retry = AsyncMock(side_effect=[1, 2])

        mock_transcript_obj = MagicMock()
        mock_aai.fetch_transcript = AsyncMock(
            return_value={
                "status": "completed",
                "text": "Test",
                "transcript_obj": mock_transcript_obj,
            }
        )
        mock_aai.convert_to_srt = AsyncMock(return_value="1\n00:00:00,000\nTest")
        mock_s3.upload_srt = AsyncMock(side_effect=RuntimeError("S3 error"))
        mock_crud.update_job_status = AsyncMock()

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        assert mock_s3.upload_srt.call_count == 2
        mock_crud.update_job_status.assert_called()

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    @patch("app.services.transcription_service.s3_storage")
    @patch("app.services.transcription_service.asyncio.sleep", new_callable=AsyncMock)
    async def test_convert_to_srt_failure_with_retry(
        self, mock_sleep, mock_s3, mock_aai, mock_crud, mock_get_settings
    ):
        """Test SRT conversion failure triggers retry."""
        mock_settings = Settings(retry_max_attempts=2, retry_backoff=[1, 2])
        mock_get_settings.return_value = mock_settings

        mock_job = create_mock_job()
        mock_crud.get_job = AsyncMock(return_value=mock_job)
        mock_crud.increment_retry = AsyncMock(side_effect=[1, 2])

        mock_transcript_obj = MagicMock()
        mock_aai.fetch_transcript = AsyncMock(
            return_value={
                "status": "completed",
                "text": "Test",
                "transcript_obj": mock_transcript_obj,
            }
        )
        mock_aai.convert_to_srt = AsyncMock(side_effect=RuntimeError("Conversion failed"))
        mock_crud.update_job_status = AsyncMock()

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        assert mock_aai.convert_to_srt.call_count == 2
        mock_crud.update_job_status.assert_called()

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    @patch("app.services.transcription_service.s3_storage")
    async def test_session_rollback_on_exception(self, mock_s3, mock_aai, mock_crud, mock_get_settings):
        """Test session rollback happens on exception."""
        mock_settings = Settings(retry_max_attempts=1, retry_backoff=[1])
        mock_get_settings.return_value = mock_settings

        mock_job = create_mock_job()
        mock_crud.get_job = AsyncMock(return_value=mock_job)
        mock_crud.increment_retry = AsyncMock(return_value=1)

        mock_aai.fetch_transcript = AsyncMock(side_effect=RuntimeError("Test error"))
        mock_crud.update_job_status = AsyncMock()

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        mock_session.rollback.assert_called()

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    @patch("app.services.transcription_service.s3_storage")
    @patch("app.services.transcription_service.asyncio.sleep", new_callable=AsyncMock)
    async def test_multiple_retries_with_different_delays(
        self, mock_sleep, mock_s3, mock_aai, mock_crud, mock_get_settings
    ):
        """Test multiple retries use correct backoff delays."""
        mock_settings = Settings(retry_max_attempts=4, retry_backoff=[1, 2, 4, 8])
        mock_get_settings.return_value = mock_settings

        mock_job = create_mock_job()
        mock_crud.get_job = AsyncMock(return_value=mock_job)
        mock_crud.increment_retry = AsyncMock(side_effect=[1, 2, 3, 3])

        mock_transcript_obj = MagicMock()
        mock_aai.fetch_transcript = AsyncMock(
            side_effect=[
                RuntimeError("Error 1"),
                RuntimeError("Error 2"),
                RuntimeError("Error 3"),
                {
                    "status": "completed",
                    "text": "Test",
                    "transcript_obj": mock_transcript_obj,
                },
            ]
        )
        mock_aai.convert_to_srt = AsyncMock(return_value="1\n00:00:00,000\nTest")
        mock_s3.upload_srt = AsyncMock(return_value="srt/test.srt")
        mock_crud.update_job_result = AsyncMock()

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        # Verify backoff delays: 1s, 2s, 4s
        assert mock_sleep.call_count == 3
        assert mock_sleep.call_args_list[0][0][0] == 1
        assert mock_sleep.call_args_list[1][0][0] == 2
        assert mock_sleep.call_args_list[2][0][0] == 4

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    async def test_job_already_at_max_retries(self, mock_aai, mock_crud, mock_get_settings):
        """Test handling when job already at max retry count."""
        mock_settings = Settings(retry_max_attempts=3, retry_backoff=[1, 2, 4])
        mock_get_settings.return_value = mock_settings

        mock_job = create_mock_job(retry_count=3)  # Already at max
        mock_crud.get_job = AsyncMock(return_value=mock_job)
        mock_crud.update_job_status = AsyncMock()

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        # Should immediately fail without attempting fetch
        mock_aai.fetch_transcript.assert_not_called()
        mock_crud.update_job_status.assert_called()
        call_args = mock_crud.update_job_status.call_args
        assert "Failed to process transcription after" in call_args[1]["error"]

    @pytest.mark.asyncio
    @patch("app.services.transcription_service.get_settings")
    @patch("app.services.transcription_service.crud")
    @patch("app.services.transcription_service.assemblyai_client")
    @patch("app.services.transcription_service.s3_storage")
    async def test_transcript_obj_missing_in_response(
        self, mock_s3, mock_aai, mock_crud, mock_get_settings
    ):
        """Test handling when transcript_obj is missing from response."""
        mock_settings = Settings(retry_max_attempts=3)
        mock_get_settings.return_value = mock_settings

        mock_crud.get_job = AsyncMock(return_value=create_mock_job())
        mock_aai.fetch_transcript = AsyncMock(
            return_value={
                "status": "completed",
                "text": "Test",
                "transcript_obj": None,  # Missing
            }
        )
        mock_aai.convert_to_srt = AsyncMock(return_value="1\n00:00:00,000\nTest")
        mock_s3.upload_srt = AsyncMock(return_value="srt/test.srt")
        mock_crud.update_job_result = AsyncMock()

        mock_session = AsyncMock()

        await process_completed_transcription(mock_session, "test-job-id", "aai-123")

        # Should still work with None transcript_obj
        mock_aai.convert_to_srt.assert_called_once_with(transcript_obj=None)
        mock_crud.update_job_result.assert_called_once()
