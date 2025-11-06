"""Pydantic schemas for transcription API."""

from datetime import datetime

from pydantic import BaseModel, Field


class TranscriptionBaseResponse(BaseModel):
    """Base response model with common transcription job fields."""

    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status (queued/processing/completed/error)")
    created_at: datetime = Field(..., description="Job creation timestamp")
    language_detection: bool = Field(..., description="Whether language detection is enabled")
    speaker_labels: bool = Field(..., description="Whether speaker diarization is enabled")


class TranscriptionJobResponse(TranscriptionBaseResponse):
    """Response model for transcription job creation."""

    audio_s3_key: str = Field(..., description="S3 key for uploaded audio file")


class TranscriptionStatusResponse(TranscriptionBaseResponse):
    """Response model for transcription job status."""

    completed_at: datetime | None = Field(None, description="Job completion timestamp")
    error_message: str | None = Field(None, description="Error message if job failed")
    srt_available: bool = Field(..., description="Whether SRT file is available for download")


class AssemblyAIWebhookPayload(BaseModel):
    """Webhook payload from AssemblyAI."""

    transcript_id: str = Field(..., description="AssemblyAI transcription ID")
    status: str = Field(..., description="Transcription status from AssemblyAI")
