"""Transcription API endpoints."""

import logging
from pathlib import Path
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import crud
from app.db.base import get_db
from app.db.models import JobStatus
from app.schemas.transcription import (
    AssemblyAIWebhookPayload,
    TranscriptionJobResponse,
    TranscriptionStatusResponse,
)
from app.services.assemblyai_client import assemblyai_client
from app.services.transcription_service import process_completed_transcription
from app.storage.s3 import s3_storage

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/transcriptions", response_model=TranscriptionJobResponse, status_code=201)
async def create_transcription_job(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    language_detection: bool = Form(False, description="Enable automatic language detection"),
    speaker_labels: bool = Form(False, description="Enable speaker diarization"),
    session: AsyncSession = Depends(get_db),
):
    """Create new transcription job.

    **Validation order:**
    1. Concurrent job limit (returns 429 if at limit)
    2. File format (returns 400 if invalid)
    3. File size (returns 413 if too large)

    **Process:**
    1. Upload audio to S3
    2. Create DB record
    3. Start AssemblyAI transcription with webhook
    4. Return job info

    Args:
        file: Audio file to transcribe
        language_detection: Enable automatic language detection
        speaker_labels: Enable speaker diarization
        session: Database session

    Returns:
        TranscriptionJobResponse with job details

    Raises:
        HTTPException: 400 (invalid format), 413 (file too large),
            429 (concurrent limit), 500 (server error)
    """
    # 1. Validate concurrent job limit FIRST (before expensive operations)
    active_count = await crud.count_active_jobs(session)
    if active_count >= settings.max_concurrent_jobs:
        logger.warning(
            "Concurrent job limit reached: %d/%d active jobs",
            active_count,
            settings.max_concurrent_jobs,
        )
        raise HTTPException(
            status_code=429,
            detail=(
                f"Maximum concurrent jobs limit reached "
                f"({settings.max_concurrent_jobs}). Please try again later."
            ),
        )

    # 2. Validate file format
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in settings.allowed_audio_formats:
        logger.warning(
            "Invalid audio format: %s (allowed: %s)", file_ext, settings.allowed_audio_formats
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid audio format '{file_ext}'. "
                f"Allowed formats: {', '.join(settings.allowed_audio_formats)}"
            ),
        )

    # 3. Validate file size (read file to check size)
    file_size = 0
    try:
        # Move to end to get size
        await file.seek(0, 2)
        file_size = await file.tell()
        # Reset to beginning for upload
        await file.seek(0)

        if file_size > settings.max_file_size:
            logger.warning(
                "File too large: %d bytes (max: %d bytes)", file_size, settings.max_file_size
            )
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File size ({file_size:,} bytes) exceeds maximum allowed "
                    f"({settings.max_file_size:,} bytes / 1GB)"
                ),
            )
    except Exception as e:
        logger.error("Error checking file size: %s", e)
        raise HTTPException(status_code=500, detail="Error processing file upload")

    # 4. Create job record in DB (to get job_id for S3 paths)
    try:
        job = await crud.create_job(
            session,
            audio_s3_key=None,  # Will update after S3 upload
            language_detection=language_detection,
            speaker_labels=speaker_labels,
        )
        job_id = job.id
        logger.info(
            "Created transcription job %s "
            "(size: %d bytes, language_detection: %s, speaker_labels: %s)",
            job_id,
            file_size,
            language_detection,
            speaker_labels,
        )
    except Exception as e:
        logger.error("Error creating job record: %s", e)
        await session.rollback()
        raise HTTPException(status_code=500, detail="Error creating transcription job")

    # 5. Upload audio to S3
    try:
        # Ensure file is at beginning before upload
        await file.seek(0)

        audio_s3_key = await s3_storage.upload_audio(job_id, file)
        logger.info("Uploaded audio to S3: %s", audio_s3_key)

        # Update job with S3 key using CRUD function
        job = await crud.update_job_status(
            session, job_id, JobStatus.QUEUED.value, audio_s3_key=audio_s3_key
        )

    except Exception as e:
        logger.error("Error uploading to S3: %s", e)
        # Mark job as error and rollback
        await session.rollback()
        try:
            await crud.update_job_status(session, job_id, JobStatus.ERROR.value, error=str(e))
        except Exception:
            pass  # Best effort to mark error
        raise HTTPException(status_code=500, detail="Error uploading audio file to storage")

    # 6. Generate presigned URL for AssemblyAI
    try:
        presigned_url = await s3_storage.generate_presigned_url(
            audio_s3_key, settings.audio_presigned_url_expiry
        )
        logger.info(
            "Generated presigned URL for audio (expires in %ds)",
            settings.audio_presigned_url_expiry,
        )
    except Exception as e:
        logger.error("Error generating presigned URL: %s", e)
        await crud.update_job_status(session, job_id, JobStatus.ERROR.value, error=str(e))
        raise HTTPException(status_code=500, detail="Error generating presigned URL")

    # 7. Start AssemblyAI transcription with webhook
    try:
        # Build webhook URL with secret token
        if not settings.webhook_base_url or not settings.webhook_secret_token:
            raise ValueError(
                "Webhook configuration missing (WEBHOOK_BASE_URL, WEBHOOK_SECRET_TOKEN)"
            )

        webhook_url = (
            f"{settings.webhook_base_url}/api/v1/webhooks/assemblyai/"
            f"{settings.webhook_secret_token}"
        )
        logger.info("Starting AssemblyAI transcription with webhook: %s", webhook_url)

        assemblyai_id = await assemblyai_client.start_transcription(
            presigned_url=presigned_url,
            webhook_url=webhook_url,
            language_detection=language_detection,
            speaker_labels=speaker_labels,
        )

        # Update job with AssemblyAI ID and set status to processing
        # Note: update_job_status commits immediately. If webhook arrives before commit
        # completes, AssemblyAI will retry (up to 10 times), so this is acceptable.
        await crud.update_job_status(
            session, job_id, JobStatus.PROCESSING.value, assemblyai_id=assemblyai_id
        )

        logger.info(
            "Started AssemblyAI transcription for job %s (AssemblyAI ID: %s)", job_id, assemblyai_id
        )

    except Exception as e:
        logger.error("Error starting AssemblyAI transcription: %s", e)
        await crud.update_job_status(
            session, job_id, JobStatus.ERROR.value, error=f"AssemblyAI error: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Error starting transcription")

    # 8. Return job info
    return TranscriptionJobResponse(
        job_id=job.id,
        status=job.status,
        created_at=job.created_at,
        audio_s3_key=job.audio_s3_key,
        language_detection=job.language_detection,
        speaker_labels=job.speaker_labels,
    )


@router.get("/transcriptions/{job_id}", response_model=TranscriptionStatusResponse)
async def get_transcription_status(
    job_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get transcription job status.

    Args:
        job_id: Job ID
        session: Database session

    Returns:
        TranscriptionStatusResponse with job status

    Raises:
        HTTPException: 404 if job not found
    """
    job = await crud.get_job(session, job_id)
    if not job:
        logger.warning("Job not found: %s", job_id)
        raise HTTPException(status_code=404, detail=f"Transcription job '{job_id}' not found")

    return TranscriptionStatusResponse(
        job_id=job.id,
        status=job.status,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        language_detection=job.language_detection,
        speaker_labels=job.speaker_labels,
        srt_available=job.status == JobStatus.COMPLETED.value and job.srt_s3_key is not None,
    )


@router.get("/transcriptions/{job_id}/srt")
async def get_transcription_srt(
    job_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get transcription SRT file via 302 redirect to presigned S3 URL.

    Args:
        job_id: Job ID
        session: Database session

    Returns:
        RedirectResponse: 302 redirect to presigned S3 URL (1 hour expiry)

    Raises:
        HTTPException: 404 (job not found), 400 (SRT not available), 500 (URL generation error)
    """
    job = await crud.get_job(session, job_id)
    if not job:
        logger.warning("Job not found: %s", job_id)
        raise HTTPException(status_code=404, detail=f"Transcription job '{job_id}' not found")

    # Check if SRT is available
    if job.status != JobStatus.COMPLETED.value or not job.srt_s3_key:
        logger.warning(
            "SRT not available for job %s (status: %s, srt_s3_key: %s)",
            job_id,
            job.status,
            job.srt_s3_key,
        )
        if job.status == JobStatus.ERROR.value:
            raise HTTPException(
                status_code=400,
                detail=f"Transcription failed: {job.error_message or 'Unknown error'}",
            )
        elif job.status in (JobStatus.QUEUED.value, JobStatus.PROCESSING.value):
            raise HTTPException(
                status_code=400,
                detail="Transcription still in progress. Please check status later.",
            )
        else:
            raise HTTPException(status_code=400, detail="SRT file not available")

    # Generate presigned URL for SRT file
    try:
        presigned_url = await s3_storage.generate_presigned_url(
            job.srt_s3_key, settings.srt_presigned_url_expiry
        )
        logger.info(
            "Generated presigned URL for SRT file (job: %s, expires in %ds)",
            job_id,
            settings.srt_presigned_url_expiry,
        )

        # Return 302 redirect
        return RedirectResponse(url=presigned_url, status_code=302)

    except Exception as e:
        logger.error("Error generating presigned URL for SRT: %s", e)
        raise HTTPException(status_code=500, detail="Error generating download URL")


@router.post("/webhooks/assemblyai/{secret_token}", status_code=200)
async def assemblyai_webhook(
    secret_token: str,
    payload: AssemblyAIWebhookPayload,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    """Handle AssemblyAI webhook completion notification.

    **Flow:**
    1. Validate secret token
    2. Return 200 OK immediately (within 10s requirement)
    3. Launch background task to process transcription

    Args:
        secret_token: Secret token from URL path
        payload: Webhook payload from AssemblyAI
        background_tasks: FastAPI background tasks
        session: Database session

    Returns:
        dict: Success message

    Raises:
        HTTPException: 401 (invalid token), 404 (job not found)
    """
    # 1. Validate secret token using constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(secret_token, settings.webhook_secret_token):
        logger.warning("Invalid webhook secret token received")
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    # 2. Look up job by AssemblyAI ID
    job = await crud.get_job_by_assemblyai_id(session, payload.transcript_id)
    if not job:
        logger.warning("Job not found for AssemblyAI ID: %s", payload.transcript_id)
        raise HTTPException(
            status_code=404, detail=f"Job not found for transcript ID '{payload.transcript_id}'"
        )

    logger.info(
        "Webhook received for job %s (AssemblyAI ID: %s, status: %s)",
        job.id,
        payload.transcript_id,
        payload.status,
    )

    # 3. Add background task to process transcription
    # Note: We pass job.id and transcript_id, not the session directly
    # Background task will create its own session
    background_tasks.add_task(
        process_transcription_background,
        job.id,
        payload.transcript_id,
    )

    # 4. Return 200 OK immediately (ACK webhook)
    logger.info("Webhook ACK sent for job %s, processing in background", job.id)
    return {"status": "ok", "job_id": job.id}


async def process_transcription_background(job_id: str, assemblyai_id: str) -> None:
    """Background task wrapper for processing completed transcription.

    Creates its own database session for the background task.

    Note: Exceptions are caught and logged. The process_completed_transcription
    function handles retry logic and updates job status to ERROR on final failure.

    Args:
        job_id: Job ID
        assemblyai_id: AssemblyAI transcription ID
    """
    # Import here to avoid circular dependency
    from app.db.base import SessionLocal

    async with SessionLocal() as session:
        try:
            await process_completed_transcription(session, job_id, assemblyai_id)
        except Exception as e:
            # Log error with full traceback for debugging
            # Note: process_completed_transcription already handles retries and updates
            # job status to ERROR. This catch block is for unexpected failures.
            logger.error(
                "Unexpected error in background transcription processing for job %s: %s",
                job_id,
                e,
                exc_info=True,
            )
            # Attempt to mark job as error (best effort)
            try:
                await crud.update_job_status(
                    session,
                    job_id,
                    JobStatus.ERROR.value,
                    error=f"Background processing failed: {str(e)}",
                )
            except Exception as mark_error_e:
                logger.error("Failed to mark job %s as error: %s", job_id, mark_error_e)
