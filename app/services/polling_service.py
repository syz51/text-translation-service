"""Background polling service for recovering stale transcription jobs."""

import asyncio
import logging

from app.core.config import settings
from app.db import crud
from app.db.base import SessionLocal
from app.services.transcription_service import process_completed_transcription

logger = logging.getLogger(__name__)


class PollingService:
    """Background service that polls for stale jobs and triggers recovery."""

    def __init__(self):
        """Initialize polling service."""
        self._task: asyncio.Task | None = None
        self._should_stop = False

    async def start(self) -> None:
        """Start the polling background task."""
        if not settings.polling_enabled:
            logger.info("Polling disabled (POLLING_ENABLED=false)")
            return

        logger.info(
            "Starting polling service (interval=%ds, threshold=%ds)",
            settings.polling_interval,
            settings.stale_job_threshold,
        )
        self._should_stop = False
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop the polling background task."""
        if not self._task:
            return

        logger.info("Stopping polling service")
        self._should_stop = True

        # Wait for current iteration to finish (with timeout)
        try:
            await asyncio.wait_for(self._task, timeout=30)
        except TimeoutError:
            logger.warning("Polling task did not stop within 30s, cancelling")
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Polling service stopped")

    async def _poll_loop(self) -> None:
        """Main polling loop that runs periodically."""
        while not self._should_stop:
            try:
                await self._poll_stale_jobs()
            except Exception as e:
                logger.error("Error in polling iteration: %s", e, exc_info=True)

            # Sleep with interruptible checks every second
            # Note: This simple loop is intentional and optimal for graceful shutdown.
            # Checking _should_stop every 1s allows fast shutdown response without
            # complex asyncio.Event() machinery. Alternative approaches don't improve this.
            for _ in range(settings.polling_interval):
                if self._should_stop:
                    break
                await asyncio.sleep(1)

    async def _poll_stale_jobs(self) -> None:
        """Poll for stale jobs and trigger recovery.

        Note on race conditions: It's safe if a webhook arrives between fetching
        stale jobs and processing them. The idempotency check in
        process_completed_transcription() handles this - whichever path (webhook
        or polling) gets there first will process the job, and the second will
        skip it. This is intentional design, not a bug.
        """
        async with SessionLocal() as session:
            try:
                # Get stale jobs
                stale_jobs = await crud.get_stale_processing_jobs(
                    session, settings.stale_job_threshold
                )

                if not stale_jobs:
                    logger.debug("No stale jobs found")
                    return

                logger.warning(
                    "Found %d stale job(s) beyond %ds threshold",
                    len(stale_jobs),
                    settings.stale_job_threshold,
                )

                # Process each stale job
                for job in stale_jobs:
                    try:
                        # Should always have assemblyai_id due to query filter, but check for safety
                        if not job.assemblyai_id:
                            logger.warning("Job %s has no assemblyai_id, skipping", job.id)
                            continue

                        logger.info(
                            "Recovering stale job %s (AssemblyAI: %s, age: %s)",
                            job.id,
                            job.assemblyai_id,
                            job.created_at,
                        )

                        # Create new session for each job to avoid transaction conflicts
                        async with SessionLocal() as job_session:
                            await process_completed_transcription(
                                job_session, job.id, job.assemblyai_id
                            )

                        logger.info("Successfully recovered stale job %s", job.id)

                    except Exception as e:
                        logger.error(
                            "Failed to recover stale job %s: %s", job.id, e, exc_info=True
                        )

            except Exception as e:
                logger.error("Error querying stale jobs: %s", e, exc_info=True)


# Global instance
polling_service = PollingService()
