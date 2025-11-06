"""Background task service for processing completed transcriptions."""

import asyncio
from datetime import UTC, datetime
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import crud
from app.db.models import JobStatus
from app.services.assemblyai_client import assemblyai_client
from app.storage.s3 import s3_storage

logger = logging.getLogger(__name__)


async def process_completed_transcription(
    session: AsyncSession, job_id: str, assemblyai_id: str
) -> None:
    """Process completed transcription with retry logic.

    This function is called after webhook ACK. It fetches the transcript,
    converts to SRT, uploads to S3, and updates the database.

    Args:
        session: Database session
        job_id: Job ID
        assemblyai_id: AssemblyAI transcription ID
    """
    logger.info(
        "Processing completed transcription for job %s (AssemblyAI: %s)", job_id, assemblyai_id
    )

    max_attempts = settings.retry_max_attempts
    backoff_delays = settings.retry_backoff

    # Fetch current retry count from DB
    job = await crud.get_job(session, job_id)
    if not job:
        logger.error("Job %s not found", job_id)
        return

    while job.retry_count < max_attempts:
        try:
            # 1. Fetch transcript from AssemblyAI
            logger.info(
                "Fetching transcript from AssemblyAI (attempt %d/%d)",
                job.retry_count + 1,
                max_attempts
            )
            transcript_data = await assemblyai_client.fetch_transcript(assemblyai_id)

            # Check if transcription succeeded
            if transcript_data["status"] == "error":
                error_msg = transcript_data.get("error") or "Unknown AssemblyAI error"
                logger.error("AssemblyAI transcription failed: %s", error_msg)
                await crud.update_job_status(
                    session, job_id, JobStatus.ERROR.value, error=error_msg
                )
                await session.commit()
                return

            # Handle non-completed states: queued/processing means webhook arrived early
            if transcript_data["status"] in ("queued", "processing"):
                logger.warning(
                    "Transcript status is '%s', webhook arrived before completion. Retrying...",
                    transcript_data["status"]
                )
                # Increment retry and continue
                job.retry_count = await crud.increment_retry(session, job_id)
                await session.commit()

                if job.retry_count < max_attempts:
                    delay = backoff_delays[min(job.retry_count - 1, len(backoff_delays) - 1)]
                    logger.info("Retrying in %ds...", delay)
                    await asyncio.sleep(delay)
                    continue
                else:
                    error_msg = (
                        f"Transcript not completed after {max_attempts} attempts "
                        f"(status: {transcript_data['status']})"
                    )
                    logger.error(error_msg)
                    await crud.update_job_status(
                        session, job_id, JobStatus.ERROR.value, error=error_msg
                    )
                    await session.commit()
                    return

            # Verify transcript is actually completed
            if transcript_data["status"] != "completed":
                error_msg = f"Unexpected transcript status: {transcript_data['status']}"
                logger.error(error_msg)
                await crud.update_job_status(
                    session, job_id, JobStatus.ERROR.value, error=error_msg
                )
                await session.commit()
                return

            # 2. Convert to SRT using pre-fetched transcript object (avoid duplicate API call)
            logger.info("Converting transcript to SRT format")
            srt_content = await assemblyai_client.convert_to_srt(
                transcript_obj=transcript_data.get("transcript_obj")
            )

            if not srt_content or not srt_content.strip():
                error_msg = "Generated SRT content is empty"
                logger.error(error_msg)
                await crud.update_job_status(
                    session, job_id, JobStatus.ERROR.value, error=error_msg
                )
                await session.commit()
                return

            # 3. Upload SRT to S3
            logger.info("Uploading SRT to S3")
            srt_s3_key = await s3_storage.upload_srt(job_id, srt_content)

            # 4. Update job with result
            logger.info("Updating job %s with result", job_id)
            await crud.update_job_result(
                session, job_id, srt_s3_key, completed_at=datetime.now(UTC)
            )
            await session.commit()

            logger.info("Successfully processed transcription for job %s", job_id)
            return

        except Exception as e:
            # Rollback transaction on error
            await session.rollback()

            logger.error(
                "Error processing transcription (attempt %d/%d): %s",
                job.retry_count + 1,
                max_attempts,
                e,
                exc_info=True,
            )

            # Increment retry count
            job.retry_count = await crud.increment_retry(session, job_id)
            await session.commit()

            if job.retry_count < max_attempts:
                # Calculate backoff delay with safe indexing
                delay = backoff_delays[min(job.retry_count - 1, len(backoff_delays) - 1)]
                logger.info("Retrying in %ds...", delay)
                await asyncio.sleep(delay)
            else:
                # Max retries reached, mark as error
                error_msg = f"Failed after {max_attempts} attempts: {str(e)}"
                logger.error(error_msg)
                await crud.update_job_status(
                    session, job_id, JobStatus.ERROR.value, error=error_msg
                )
                await session.commit()
                return

    # Should not reach here, but just in case
    error_msg = f"Failed to process transcription after {max_attempts} attempts"
    logger.error(error_msg)
    await crud.update_job_status(session, job_id, JobStatus.ERROR.value, error=error_msg)
    await session.commit()
