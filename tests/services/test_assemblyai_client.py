"""Unit tests for AssemblyAI client."""

from unittest.mock import MagicMock, patch

import assemblyai as aai
import pytest

from app.services.assemblyai_client import AssemblyAIClient


class TestAssemblyAIClientInitialization:
    """Test client initialization and configuration."""

    def test_init_lazy_initialization(self):
        """Test client uses lazy initialization."""
        client = AssemblyAIClient()
        assert client._initialized is False
        assert client.transcriber is None

    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    def test_ensure_initialized_success(self, mock_aai, mock_settings):
        """Test successful initialization."""
        mock_settings.assemblyai_api_key = "test_api_key"
        mock_transcriber = MagicMock()
        mock_aai.Transcriber.return_value = mock_transcriber

        client = AssemblyAIClient()
        client._ensure_initialized()

        assert client._initialized is True
        assert client.transcriber == mock_transcriber
        assert mock_aai.settings.api_key == "test_api_key"

    @patch("app.services.assemblyai_client.settings")
    def test_ensure_initialized_no_api_key(self, mock_settings):
        """Test initialization fails without API key."""
        mock_settings.assemblyai_api_key = None

        client = AssemblyAIClient()

        with pytest.raises(ValueError, match="ASSEMBLYAI_API_KEY not configured"):
            client._ensure_initialized()

    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    def test_ensure_initialized_idempotent(self, mock_aai, mock_settings):
        """Test _ensure_initialized is idempotent."""
        mock_settings.assemblyai_api_key = "test_key"
        mock_aai.Transcriber.return_value = MagicMock()

        client = AssemblyAIClient()
        client._ensure_initialized()
        client._ensure_initialized()  # Call again

        # Should only initialize once
        assert mock_aai.Transcriber.call_count == 1


class TestStartTranscription:
    """Test start_transcription method."""

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_start_transcription_success(self, mock_aai, mock_settings):
        """Test successful transcription start."""
        mock_settings.assemblyai_api_key = "test_key"

        # Mock transcript response
        mock_transcript = MagicMock()
        mock_transcript.id = "test-transcript-id"

        mock_transcriber = MagicMock()
        mock_transcriber.submit.return_value = mock_transcript
        mock_aai.Transcriber.return_value = mock_transcriber

        client = AssemblyAIClient()
        result = await client.start_transcription(
            presigned_url="https://s3.example.com/audio.mp3",
            webhook_url="https://api.example.com/webhook",
            language_detection=True,
            speaker_labels=False,
        )

        assert result == "test-transcript-id"
        mock_transcriber.submit.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_start_transcription_no_id_returned(self, mock_aai, mock_settings):
        """Test error when no transcript ID returned."""
        mock_settings.assemblyai_api_key = "test_key"

        mock_transcript = MagicMock()
        mock_transcript.id = None  # No ID

        mock_transcriber = MagicMock()
        mock_transcriber.submit.return_value = mock_transcript
        mock_aai.Transcriber.return_value = mock_transcriber
        mock_aai.TranscriptError = aai.TranscriptError

        client = AssemblyAIClient()

        with pytest.raises(aai.TranscriptError, match="no ID returned"):
            await client.start_transcription(
                presigned_url="https://s3.example.com/audio.mp3",
                webhook_url="https://api.example.com/webhook",
            )

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_start_transcription_transcript_error(self, mock_aai, mock_settings):
        """Test handling of TranscriptError."""
        mock_settings.assemblyai_api_key = "test_key"

        mock_transcriber = MagicMock()
        mock_transcriber.submit.side_effect = aai.TranscriptError("API error")
        mock_aai.Transcriber.return_value = mock_transcriber
        mock_aai.TranscriptError = aai.TranscriptError

        client = AssemblyAIClient()

        with pytest.raises(aai.TranscriptError, match="API error"):
            await client.start_transcription(
                presigned_url="https://s3.example.com/audio.mp3",
                webhook_url="https://api.example.com/webhook",
            )

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_start_transcription_generic_error(self, mock_aai, mock_settings):
        """Test handling of generic exceptions."""
        mock_settings.assemblyai_api_key = "test_key"

        mock_transcriber = MagicMock()
        mock_transcriber.submit.side_effect = RuntimeError("Unexpected error")
        mock_aai.Transcriber.return_value = mock_transcriber
        mock_aai.TranscriptError = aai.TranscriptError

        client = AssemblyAIClient()

        with pytest.raises(RuntimeError, match="Unexpected error"):
            await client.start_transcription(
                presigned_url="https://s3.example.com/audio.mp3",
                webhook_url="https://api.example.com/webhook",
            )

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    async def test_start_transcription_not_initialized(self, mock_settings):
        """Test error when transcriber not initialized."""
        mock_settings.assemblyai_api_key = None

        client = AssemblyAIClient()

        with pytest.raises(ValueError, match="ASSEMBLYAI_API_KEY not configured"):
            await client.start_transcription(
                presigned_url="https://s3.example.com/audio.mp3",
                webhook_url="https://api.example.com/webhook",
            )


class TestFetchTranscript:
    """Test fetch_transcript method."""

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_fetch_transcript_success(self, mock_aai, mock_settings):
        """Test successful transcript fetch."""
        mock_settings.assemblyai_api_key = "test_key"

        # Mock transcript with all fields
        mock_transcript = MagicMock()
        mock_transcript.id = "test-id"
        mock_transcript.status.value = "completed"
        mock_transcript.text = "Test transcript text"
        mock_transcript.error = None
        mock_transcript.words = [{"text": "test"}]
        mock_transcript.utterances = [{"text": "test"}]
        mock_transcript.json_response = {"language_code": "en"}

        mock_aai.Transcript.get_by_id.return_value = mock_transcript
        mock_aai.Transcriber.return_value = MagicMock()

        client = AssemblyAIClient()
        result = await client.fetch_transcript("test-id")

        assert result["id"] == "test-id"
        assert result["status"] == "completed"
        assert result["text"] == "Test transcript text"
        assert result["error"] is None
        assert result["language_code"] == "en"
        assert result["transcript_obj"] == mock_transcript

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_fetch_transcript_no_language_code(self, mock_aai, mock_settings):
        """Test fetch transcript without language_code."""
        mock_settings.assemblyai_api_key = "test_key"

        mock_transcript = MagicMock()
        mock_transcript.id = "test-id"
        mock_transcript.status.value = "completed"
        mock_transcript.text = "Test"
        mock_transcript.error = None
        mock_transcript.words = []
        mock_transcript.utterances = []
        mock_transcript.json_response = None  # No json_response

        mock_aai.Transcript.get_by_id.return_value = mock_transcript
        mock_aai.Transcriber.return_value = MagicMock()

        client = AssemblyAIClient()
        result = await client.fetch_transcript("test-id")

        assert result["language_code"] is None

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_fetch_transcript_error(self, mock_aai, mock_settings):
        """Test fetch transcript with TranscriptError."""
        mock_settings.assemblyai_api_key = "test_key"

        mock_aai.Transcript.get_by_id.side_effect = aai.TranscriptError("Fetch failed")
        mock_aai.Transcriber.return_value = MagicMock()
        mock_aai.TranscriptError = aai.TranscriptError

        client = AssemblyAIClient()

        with pytest.raises(aai.TranscriptError, match="Fetch failed"):
            await client.fetch_transcript("test-id")

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_fetch_transcript_generic_error(self, mock_aai, mock_settings):
        """Test fetch transcript with generic exception."""
        mock_settings.assemblyai_api_key = "test_key"

        mock_aai.Transcript.get_by_id.side_effect = RuntimeError("Unexpected")
        mock_aai.Transcriber.return_value = MagicMock()
        mock_aai.TranscriptError = aai.TranscriptError

        client = AssemblyAIClient()

        with pytest.raises(RuntimeError, match="Unexpected"):
            await client.fetch_transcript("test-id")


class TestConvertToSRT:
    """Test convert_to_srt method."""

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_convert_to_srt_with_transcript_obj(self, mock_aai, mock_settings):
        """Test SRT conversion with pre-fetched transcript object."""
        mock_settings.assemblyai_api_key = "test_key"

        mock_transcript = MagicMock()
        mock_transcript.id = "test-id"
        mock_transcript.export_subtitles_srt.return_value = "1\n00:00:00,000 --> 00:00:01,000\nTest"

        mock_aai.Transcriber.return_value = MagicMock()

        client = AssemblyAIClient()
        result = await client.convert_to_srt(transcript_obj=mock_transcript)

        assert "1\n00:00:00,000" in result
        mock_transcript.export_subtitles_srt.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_convert_to_srt_with_assemblyai_id(self, mock_aai, mock_settings):
        """Test SRT conversion by fetching transcript by ID."""
        mock_settings.assemblyai_api_key = "test_key"

        mock_transcript = MagicMock()
        mock_transcript.id = "test-id"
        mock_transcript.export_subtitles_srt.return_value = "1\n00:00:00,000 --> 00:00:01,000\nTest"

        mock_aai.Transcript.get_by_id.return_value = mock_transcript
        mock_aai.Transcriber.return_value = MagicMock()

        client = AssemblyAIClient()
        result = await client.convert_to_srt(assemblyai_id="test-id")

        assert "1\n00:00:00,000" in result
        mock_aai.Transcript.get_by_id.assert_called_once_with("test-id")

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_convert_to_srt_no_params(self, mock_aai, mock_settings):
        """Test error when neither transcript_obj nor assemblyai_id provided."""
        mock_settings.assemblyai_api_key = "test_key"
        mock_aai.Transcriber.return_value = MagicMock()
        mock_aai.TranscriptError = aai.TranscriptError

        client = AssemblyAIClient()

        with pytest.raises(ValueError, match="Must provide either"):
            await client.convert_to_srt()

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_convert_to_srt_transcript_error(self, mock_aai, mock_settings):
        """Test SRT conversion with TranscriptError."""
        mock_settings.assemblyai_api_key = "test_key"

        mock_transcript = MagicMock()
        mock_transcript.export_subtitles_srt.side_effect = aai.TranscriptError("Export failed")

        mock_aai.Transcriber.return_value = MagicMock()
        mock_aai.TranscriptError = aai.TranscriptError

        client = AssemblyAIClient()

        with pytest.raises(aai.TranscriptError, match="Export failed"):
            await client.convert_to_srt(transcript_obj=mock_transcript)

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_convert_to_srt_generic_error(self, mock_aai, mock_settings):
        """Test SRT conversion with generic exception."""
        mock_settings.assemblyai_api_key = "test_key"

        mock_transcript = MagicMock()
        mock_transcript.export_subtitles_srt.side_effect = RuntimeError("Unexpected")

        mock_aai.Transcriber.return_value = MagicMock()
        mock_aai.TranscriptError = aai.TranscriptError

        client = AssemblyAIClient()

        with pytest.raises(RuntimeError, match="Unexpected"):
            await client.convert_to_srt(transcript_obj=mock_transcript)


class TestConnectivity:
    """Test test_connectivity method."""

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_connectivity_success_404(self, mock_aai, mock_settings):
        """Test connectivity with expected 404 (valid API key)."""
        mock_settings.assemblyai_api_key = "test_key"

        # Simulate 404 error (expected for test ID)
        mock_error = aai.TranscriptError("Transcript not found")
        mock_aai.Transcript.get_by_id.side_effect = mock_error
        mock_aai.Transcriber.return_value = MagicMock()
        mock_aai.TranscriptError = aai.TranscriptError

        client = AssemblyAIClient()
        result = await client.test_connectivity()

        assert result is True

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_connectivity_auth_failure_401(self, mock_aai, mock_settings):
        """Test connectivity with 401 (invalid API key)."""
        mock_settings.assemblyai_api_key = "invalid_key"

        mock_error = aai.TranscriptError("401 Unauthorized")
        mock_aai.Transcript.get_by_id.side_effect = mock_error
        mock_aai.Transcriber.return_value = MagicMock()
        mock_aai.TranscriptError = aai.TranscriptError

        client = AssemblyAIClient()
        result = await client.test_connectivity()

        assert result is False

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_connectivity_auth_failure_403(self, mock_aai, mock_settings):
        """Test connectivity with 403 (forbidden)."""
        mock_settings.assemblyai_api_key = "test_key"

        mock_error = aai.TranscriptError("403 Forbidden")
        mock_aai.Transcript.get_by_id.side_effect = mock_error
        mock_aai.Transcriber.return_value = MagicMock()
        mock_aai.TranscriptError = aai.TranscriptError

        client = AssemblyAIClient()
        result = await client.test_connectivity()

        assert result is False

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_connectivity_other_transcript_error(self, mock_aai, mock_settings):
        """Test connectivity with other TranscriptError."""
        mock_settings.assemblyai_api_key = "test_key"

        mock_error = aai.TranscriptError("500 Internal Server Error")
        mock_aai.Transcript.get_by_id.side_effect = mock_error
        mock_aai.Transcriber.return_value = MagicMock()
        mock_aai.TranscriptError = aai.TranscriptError

        client = AssemblyAIClient()
        result = await client.test_connectivity()

        assert result is False

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_connectivity_generic_exception(self, mock_aai, mock_settings):
        """Test connectivity with generic exception."""
        mock_settings.assemblyai_api_key = "test_key"

        mock_aai.Transcript.get_by_id.side_effect = RuntimeError("Network error")
        mock_aai.Transcriber.return_value = MagicMock()

        client = AssemblyAIClient()
        result = await client.test_connectivity()

        assert result is False

    @pytest.mark.asyncio
    @patch("app.services.assemblyai_client.settings")
    @patch("app.services.assemblyai_client.aai")
    async def test_connectivity_no_error(self, mock_aai, mock_settings):
        """Test connectivity when no error raised (unexpected but handled)."""
        mock_settings.assemblyai_api_key = "test_key"

        mock_transcript = MagicMock()
        mock_aai.Transcript.get_by_id.return_value = mock_transcript
        mock_aai.Transcriber.return_value = MagicMock()

        client = AssemblyAIClient()
        result = await client.test_connectivity()

        assert result is True
