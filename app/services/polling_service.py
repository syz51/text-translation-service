"""Background polling service for recovering stale transcription jobs."""

import asyncio
import logging

from app.core.config import Settings, get_settings
from app.db import crud
from app.db.base import SessionLocal
from app.services.transcription_service import process_completed_transcription

logger = logging.getLogger(__name__)


class PollingService:
    """Background service that polls for stale jobs and triggers recovery."""

    def __init__(self, settings: Settings | None = None):
        """Initialize polling service.

        Args:
            settings: Optional Settings instance (uses get_settings() if not provided)
        """
        self._task: asyncio.Task | None = None
        self._should_stop = False
        self._settings = settings

    async def start(self) -> None:
        """Start the polling background task."""
        settings = self._settings if self._settings is not None else get_settings()
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
        settings = self._settings if self._settings is not None else get_settings()
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
        """Poll for jobs and trigger completion processing.

        Strategy:
        - If webhooks configured: Only check stale jobs (failsafe recovery)
        - If no webhooks: Actively poll ALL processing jobs (primary completion mechanism)

        Note on race conditions: It's safe if a webhook arrives between fetching
        jobs and processing them. The idempotency check in
        process_completed_transcription() handles this - whichever path (webhook
        or polling) gets there first will process the job, and the second will
        skip it. This is intentional design, not a bug.
        """
        settings = self._settings if self._settings is not None else get_settings()
        async with SessionLocal() as session:
            try:
                # Determine polling strategy based on webhook configuration
                webhook_configured = bool(
                    settings.webhook_base_url and settings.webhook_secret_token
                )

                if webhook_configured:
                    # Stale recovery mode: Only check old jobs (webhooks handle recent ones)
                    jobs = await crud.get_stale_processing_jobs(
                        session, settings.stale_job_threshold
                    )
                    if jobs:
                        logger.warning(
                            "Found %d stale job(s) beyond %ds threshold (webhook recovery)",
                            len(jobs),
                            settings.stale_job_threshold,
                        )
                    else:
                        logger.debug("No stale jobs found (webhook mode)")
                else:
                    # Active polling mode: Check ALL processing jobs (no webhooks)
                    jobs = await crud.get_all_processing_jobs(session)
                    if jobs:
                        logger.info(
                            "Found %d processing job(s) to check (active polling mode)", len(jobs)
                        )
                    else:
                        logger.debug("No processing jobs found (active polling mode)")

                if not jobs:
                    return

                # Process each job
                for job in jobs:
                    try:
                        # Should always have assemblyai_id due to query filter, but check for safety
                        if not job.assemblyai_id:
                            logger.warning("Job %s has no assemblyai_id, skipping", job.id)
                            continue

                        logger.info(
                            "Checking job %s (AssemblyAI: %s, created: %s)",
                            job.id,
                            job.assemblyai_id,
                            job.created_at,
                        )

                        # Create new session for each job to avoid transaction conflicts
                        async with SessionLocal() as job_session:
                            await process_completed_transcription(
                                job_session, job.id, job.assemblyai_id, settings=settings
                            )

                        logger.info("Successfully processed job %s", job.id)

                    except Exception as e:
                        logger.error("Failed to process job %s: %s", job.id, e, exc_info=True)

            except Exception as e:
                logger.error("Error querying jobs: %s", e, exc_info=True)


# Global instance
polling_service = PollingService()
