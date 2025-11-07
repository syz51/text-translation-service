"""Tests for CRUD operations related to polling."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.db.models import JobStatus


@pytest.mark.asyncio
async def test_get_stale_processing_jobs_empty(db_session: AsyncSession):
    """Test get_stale_processing_jobs returns empty list when no stale jobs."""
    stale_jobs = await crud.get_stale_processing_jobs(db_session, stale_threshold_seconds=7200)
    assert stale_jobs == []


@pytest.mark.asyncio
async def test_get_stale_processing_jobs_finds_stale(db_session: AsyncSession):
    """Test get_stale_processing_jobs finds stale jobs."""
    # Create a job that's 3 hours old (stale)
    stale_job = await crud.create_job(db_session, audio_s3_key="audio/stale.mp3")
    stale_job.status = JobStatus.PROCESSING.value
    stale_job.assemblyai_id = "assemblyai-123"
    stale_job.created_at = datetime.now(UTC) - timedelta(hours=3)
    await db_session.commit()

    # Query with 2 hour threshold
    stale_jobs = await crud.get_stale_processing_jobs(db_session, stale_threshold_seconds=7200)
    assert len(stale_jobs) == 1
    assert stale_jobs[0].id == stale_job.id


@pytest.mark.asyncio
async def test_get_stale_processing_jobs_ignores_recent(db_session: AsyncSession):
    """Test get_stale_processing_jobs ignores recent jobs."""
    # Create a job that's 1 hour old (not stale)
    recent_job = await crud.create_job(db_session, audio_s3_key="audio/recent.mp3")
    recent_job.status = JobStatus.PROCESSING.value
    recent_job.assemblyai_id = "assemblyai-456"
    recent_job.created_at = datetime.now(UTC) - timedelta(hours=1)
    await db_session.commit()

    # Query with 2 hour threshold
    stale_jobs = await crud.get_stale_processing_jobs(db_session, stale_threshold_seconds=7200)
    assert len(stale_jobs) == 0


@pytest.mark.asyncio
async def test_get_stale_processing_jobs_ignores_completed(db_session: AsyncSession):
    """Test get_stale_processing_jobs ignores completed jobs."""
    # Create a completed job that's 3 hours old
    completed_job = await crud.create_job(db_session, audio_s3_key="audio/completed.mp3")
    completed_job.status = JobStatus.COMPLETED.value
    completed_job.assemblyai_id = "assemblyai-789"
    completed_job.srt_s3_key = "srt/completed.srt"
    completed_job.created_at = datetime.now(UTC) - timedelta(hours=3)
    completed_job.completed_at = datetime.now(UTC) - timedelta(hours=2)
    await db_session.commit()

    # Query with 2 hour threshold
    stale_jobs = await crud.get_stale_processing_jobs(db_session, stale_threshold_seconds=7200)
    assert len(stale_jobs) == 0


@pytest.mark.asyncio
async def test_get_stale_processing_jobs_ignores_queued(db_session: AsyncSession):
    """Test get_stale_processing_jobs ignores queued jobs."""
    # Create a queued job that's 3 hours old
    queued_job = await crud.create_job(db_session, audio_s3_key="audio/queued.mp3")
    queued_job.status = JobStatus.QUEUED.value
    queued_job.created_at = datetime.now(UTC) - timedelta(hours=3)
    await db_session.commit()

    # Query with 2 hour threshold
    stale_jobs = await crud.get_stale_processing_jobs(db_session, stale_threshold_seconds=7200)
    assert len(stale_jobs) == 0


@pytest.mark.asyncio
async def test_get_stale_processing_jobs_ignores_no_assemblyai_id(db_session: AsyncSession):
    """Test get_stale_processing_jobs ignores jobs without assemblyai_id."""
    # Create a processing job without assemblyai_id
    job = await crud.create_job(db_session, audio_s3_key="audio/no-id.mp3")
    job.status = JobStatus.PROCESSING.value
    job.created_at = datetime.now(UTC) - timedelta(hours=3)
    # assemblyai_id is None
    await db_session.commit()

    # Query with 2 hour threshold
    stale_jobs = await crud.get_stale_processing_jobs(db_session, stale_threshold_seconds=7200)
    assert len(stale_jobs) == 0


@pytest.mark.asyncio
async def test_get_stale_processing_jobs_multiple(db_session: AsyncSession):
    """Test get_stale_processing_jobs returns multiple stale jobs."""
    # Create 3 stale jobs
    for i in range(3):
        job = await crud.create_job(db_session, audio_s3_key=f"audio/stale-{i}.mp3")
        job.status = JobStatus.PROCESSING.value
        job.assemblyai_id = f"assemblyai-{i}"
        job.created_at = datetime.now(UTC) - timedelta(hours=3)
        await db_session.commit()

    # Query with 2 hour threshold
    stale_jobs = await crud.get_stale_processing_jobs(db_session, stale_threshold_seconds=7200)
    assert len(stale_jobs) == 3
