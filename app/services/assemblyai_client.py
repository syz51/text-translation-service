"""AssemblyAI client for transcription operations."""

import logging
from typing import Any

import assemblyai as aai

from app.core.config import settings

logger = logging.getLogger(__name__)


class AssemblyAIClient:
    """Client for interacting with AssemblyAI API."""

    def __init__(self):
        """Initialize AssemblyAI client with API key."""
        if settings.assemblyai_api_key:
            aai.settings.api_key = settings.assemblyai_api_key
        self.transcriber = aai.Transcriber()

    async def start_transcription(
        self,
        presigned_url: str,
        webhook_url: str,
        language_detection: bool = False,
        speaker_labels: bool = False,
    ) -> str:
        """Start transcription job with AssemblyAI.

        Args:
            presigned_url: S3 presigned URL for audio file
            webhook_url: Webhook URL for completion notification
            language_detection: Enable automatic language detection
            speaker_labels: Enable speaker diarization

        Returns:
            AssemblyAI transcription ID

        Raises:
            Exception: If transcription start fails
        """
        try:
            config = aai.TranscriptionConfig(
                language_detection=language_detection,
                speaker_labels=speaker_labels,
                webhook_url=webhook_url,
            )

            # Submit transcription (non-blocking, returns immediately)
            transcript = self.transcriber.submit(presigned_url, config=config)

            logger.info(
                "Started AssemblyAI transcription: %s (language_detection=%s, speaker_labels=%s)",
                transcript.id,
                language_detection,
                speaker_labels,
            )
            return transcript.id

        except Exception as e:
            logger.error("Failed to start AssemblyAI transcription: %s", e)
            raise

    async def fetch_transcript(self, assemblyai_id: str) -> dict[str, Any]:
        """Fetch completed transcript from AssemblyAI.

        Args:
            assemblyai_id: AssemblyAI transcription ID

        Returns:
            Transcript data as dictionary with status, text, error, etc.

        Raises:
            Exception: If fetch fails
        """
        try:
            transcript = aai.Transcript.get_by_id(assemblyai_id)

            result = {
                "id": transcript.id,
                "status": transcript.status.value,
                "text": transcript.text,
                "error": transcript.error,
                "words": transcript.words,
                "utterances": transcript.utterances if hasattr(transcript, "utterances") else None,
                "language_code": (
                    transcript.language_code if hasattr(transcript, "language_code") else None
                ),
            }

            logger.info("Fetched transcript %s with status: %s", assemblyai_id, result["status"])
            return result

        except Exception as e:
            logger.error("Failed to fetch transcript %s: %s", assemblyai_id, e)
            raise

    async def convert_to_srt(self, assemblyai_id: str) -> str:
        """Convert AssemblyAI transcript to SRT format.

        Args:
            assemblyai_id: AssemblyAI transcription ID

        Returns:
            SRT formatted subtitle content

        Raises:
            Exception: If conversion fails
        """
        try:
            transcript = aai.Transcript.get_by_id(assemblyai_id)

            # Use built-in SRT export
            srt_content = transcript.export_subtitles_srt()

            logger.info("Converted transcript %s to SRT format", assemblyai_id)
            return srt_content

        except Exception as e:
            logger.error("Failed to convert transcript %s to SRT: %s", assemblyai_id, e)
            raise

    async def test_connectivity(self) -> bool:
        """Test AssemblyAI API connectivity.

        Returns:
            True if connected, False otherwise
        """
        try:
            # Try to list transcripts with limit 1 as a connectivity test
            self.transcriber.list_transcripts(aai.ListTranscriptParameters(limit=1))

            logger.info("AssemblyAI connectivity test successful")
            return True

        except Exception as e:
            logger.error("AssemblyAI connectivity test failed: %s", e)
            return False


# Global AssemblyAI client instance
assemblyai_client = AssemblyAIClient()
