"""CRUD operations for transcription jobs."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobStatus, TranscriptionJob


async def create_job(
    session: AsyncSession,
    audio_s3_key: str,
    language_detection: bool = False,
    speaker_labels: bool = False,
) -> TranscriptionJob:
    """Create a new transcription job.

    Args:
        session: Database session
        audio_s3_key: S3 key for the audio file
        language_detection: Enable language detection
        speaker_labels: Enable speaker labels

    Returns:
        Created TranscriptionJob
    """
    job = TranscriptionJob(
        audio_s3_key=audio_s3_key,
        language_detection=language_detection,
        speaker_labels=speaker_labels,
        status=JobStatus.QUEUED.value,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def get_job(session: AsyncSession, job_id: str) -> TranscriptionJob | None:
    """Get a transcription job by ID.

    Args:
        session: Database session
        job_id: Job ID

    Returns:
        TranscriptionJob or None if not found
    """
    result = await session.execute(select(TranscriptionJob).where(TranscriptionJob.id == job_id))
    return result.scalar_one_or_none()


async def get_job_by_assemblyai_id(
    session: AsyncSession, assemblyai_id: str
) -> TranscriptionJob | None:
    """Get a transcription job by AssemblyAI ID.

    Args:
        session: Database session
        assemblyai_id: AssemblyAI transcription ID

    Returns:
        TranscriptionJob or None if not found
    """
    result = await session.execute(
        select(TranscriptionJob).where(TranscriptionJob.assemblyai_id == assemblyai_id)
    )
    return result.scalar_one_or_none()


async def update_job_status(
    session: AsyncSession,
    job_id: str,
    status: str,
    error: str | None = None,
    assemblyai_id: str | None = None,
) -> TranscriptionJob | None:
    """Update job status and optional error message.

    Args:
        session: Database session
        job_id: Job ID
        status: New status
        error: Optional error message
        assemblyai_id: Optional AssemblyAI ID

    Returns:
        Updated TranscriptionJob or None if not found
    """
    job = await get_job(session, job_id)
    if not job:
        return None

    job.status = status
    if error is not None:
        job.error_message = error
    if assemblyai_id is not None:
        job.assemblyai_id = assemblyai_id

    await session.commit()
    await session.refresh(job)
    return job


async def update_job_result(
    session: AsyncSession,
    job_id: str,
    srt_s3_key: str,
    completed_at: datetime | None = None,
) -> TranscriptionJob | None:
    """Update job with transcription result.

    Args:
        session: Database session
        job_id: Job ID
        srt_s3_key: S3 key for the SRT file
        completed_at: Completion timestamp (defaults to now)

    Returns:
        Updated TranscriptionJob or None if not found
    """
    job = await get_job(session, job_id)
    if not job:
        return None

    job.status = JobStatus.COMPLETED.value
    job.srt_s3_key = srt_s3_key
    job.completed_at = completed_at or datetime.utcnow()

    await session.commit()
    await session.refresh(job)
    return job


async def increment_retry(session: AsyncSession, job_id: str) -> int:
    """Increment retry count for a job.

    Args:
        session: Database session
        job_id: Job ID

    Returns:
        New retry count, or -1 if job not found
    """
    job = await get_job(session, job_id)
    if not job:
        return -1

    job.retry_count += 1
    await session.commit()
    await session.refresh(job)
    return job.retry_count


async def count_active_jobs(session: AsyncSession) -> int:
    """Count jobs with status 'queued' or 'processing'.

    Args:
        session: Database session

    Returns:
        Count of active jobs
    """
    result = await session.execute(
        select(func.count(TranscriptionJob.id)).where(
            TranscriptionJob.status.in_([JobStatus.QUEUED.value, JobStatus.PROCESSING.value])
        )
    )
    return result.scalar_one()
