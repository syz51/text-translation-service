"""AssemblyAI client for transcription operations."""

import asyncio
import logging
import time
from typing import Any

import assemblyai as aai

from app.core.config import settings

logger = logging.getLogger(__name__)


class AssemblyAIClient:
    """Client for interacting with AssemblyAI API."""

    def __init__(self):
        """Initialize AssemblyAI client with API key.

        Raises:
            ValueError: If API key not configured
        """
        if not settings.assemblyai_api_key:
            raise ValueError("ASSEMBLYAI_API_KEY not configured")
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
            aai.TranscriptError: If transcription start fails
        """
        try:
            config = aai.TranscriptionConfig(
                language_detection=language_detection,
                speaker_labels=speaker_labels,
                webhook_url=webhook_url,
            )

            # Submit transcription - wrap sync call in thread to avoid blocking
            transcript = await asyncio.to_thread(
                self.transcriber.submit, presigned_url, config=config
            )

            logger.info(
                "Started AssemblyAI transcription: %s (language_detection=%s, speaker_labels=%s)",
                transcript.id,
                language_detection,
                speaker_labels,
            )
            return transcript.id

        except aai.TranscriptError as e:
            logger.error("Failed to start AssemblyAI transcription: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error starting AssemblyAI transcription: %s", e)
            raise

    async def fetch_transcript(self, assemblyai_id: str) -> dict[str, Any]:
        """Fetch completed transcript from AssemblyAI.

        Args:
            assemblyai_id: AssemblyAI transcription ID

        Returns:
            Transcript data as dictionary with status, text, error, transcript object, etc.

        Raises:
            aai.TranscriptError: If fetch fails
        """
        try:
            start_time = time.perf_counter()

            # Wrap sync call in thread to avoid blocking
            transcript = await asyncio.to_thread(aai.Transcript.get_by_id, assemblyai_id)

            elapsed = time.perf_counter() - start_time

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
                "transcript_obj": transcript,  # Include for convert_to_srt to avoid duplicate fetch
            }

            logger.info(
                "Fetched transcript %s with status: %s (%.2fs)",
                assemblyai_id,
                result["status"],
                elapsed
            )
            return result

        except aai.TranscriptError as e:
            logger.error("Failed to fetch transcript %s: %s", assemblyai_id, e)
            raise
        except Exception as e:
            logger.error("Unexpected error fetching transcript %s: %s", assemblyai_id, e)
            raise

    async def convert_to_srt(
        self,
        transcript_obj: Any = None,
        assemblyai_id: str | None = None
    ) -> str:
        """Convert AssemblyAI transcript to SRT format.

        Args:
            transcript_obj: Pre-fetched transcript object (preferred to avoid duplicate API call)
            assemblyai_id: AssemblyAI transcription ID (if transcript_obj not provided)

        Returns:
            SRT formatted subtitle content

        Raises:
            ValueError: If neither transcript_obj nor assemblyai_id provided
            aai.TranscriptError: If conversion fails
        """
        try:
            start_time = time.perf_counter()

            # Use provided transcript object or fetch by ID
            if transcript_obj is None:
                if assemblyai_id is None:
                    raise ValueError("Must provide either transcript_obj or assemblyai_id")
                transcript = await asyncio.to_thread(aai.Transcript.get_by_id, assemblyai_id)
                transcript_id = assemblyai_id
            else:
                transcript = transcript_obj
                transcript_id = transcript.id

            # Wrap sync SRT export call in thread
            srt_content = await asyncio.to_thread(transcript.export_subtitles_srt)

            elapsed = time.perf_counter() - start_time
            srt_size = len(srt_content) if srt_content else 0

            logger.info(
                "Converted transcript %s to SRT format: %d bytes (%.2fs)",
                transcript_id,
                srt_size,
                elapsed
            )
            return srt_content

        except aai.TranscriptError as e:
            logger.error("Failed to convert transcript to SRT: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error converting transcript to SRT: %s", e)
            raise

    async def test_connectivity(self) -> bool:
        """Test AssemblyAI API connectivity.

        Returns:
            True if connected, False otherwise
        """
        try:
            # Try to list transcripts with limit 1 as a connectivity test - wrap in thread
            await asyncio.to_thread(
                self.transcriber.list_transcripts,
                aai.ListTranscriptParameters(limit=1)
            )

            logger.info("AssemblyAI connectivity test successful")
            return True

        except Exception as e:
            logger.error("AssemblyAI connectivity test failed: %s", e)
            return False


# Global AssemblyAI client instance
assemblyai_client = AssemblyAIClient()
