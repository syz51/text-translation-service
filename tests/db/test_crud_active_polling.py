"""Tests for active polling CRUD operations."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.db.models import JobStatus


@pytest.mark.asyncio
async def test_get_all_processing_jobs_empty(db_session: AsyncSession):
    """Test get_all_processing_jobs returns empty list when no processing jobs."""
    jobs = await crud.get_all_processing_jobs(db_session)
    assert jobs == []


@pytest.mark.asyncio
async def test_get_all_processing_jobs_finds_processing(db_session: AsyncSession):
    """Test get_all_processing_jobs finds all processing jobs regardless of age."""
    # Create recent processing job
    recent_job = await crud.create_job(db_session, audio_s3_key="audio/recent.mp3")
    await crud.update_job_status(
        db_session, recent_job.id, JobStatus.PROCESSING.value, assemblyai_id="recent-123"
    )

    # Create old processing job
    old_job = await crud.create_job(db_session, audio_s3_key="audio/old.mp3")
    await crud.update_job_status(
        db_session, old_job.id, JobStatus.PROCESSING.value, assemblyai_id="old-123"
    )
    # Manually update created_at to 3 hours ago
    old_job.created_at = datetime.now(UTC) - timedelta(hours=3)
    await db_session.commit()

    # Should find both jobs
    jobs = await crud.get_all_processing_jobs(db_session)
    assert len(jobs) == 2
    job_ids = {job.id for job in jobs}
    assert recent_job.id in job_ids
    assert old_job.id in job_ids


@pytest.mark.asyncio
async def test_get_all_processing_jobs_ignores_completed(db_session: AsyncSession):
    """Test get_all_processing_jobs ignores completed jobs."""
    # Create processing job
    processing_job = await crud.create_job(db_session, audio_s3_key="audio/processing.mp3")
    await crud.update_job_status(
        db_session, processing_job.id, JobStatus.PROCESSING.value, assemblyai_id="proc-123"
    )

    # Create completed job
    completed_job = await crud.create_job(db_session, audio_s3_key="audio/completed.mp3")
    await crud.update_job_result(db_session, completed_job.id, "srt/completed.srt")

    jobs = await crud.get_all_processing_jobs(db_session)
    assert len(jobs) == 1
    assert jobs[0].id == processing_job.id


@pytest.mark.asyncio
async def test_get_all_processing_jobs_ignores_queued(db_session: AsyncSession):
    """Test get_all_processing_jobs ignores queued jobs."""
    # Create processing job
    processing_job = await crud.create_job(db_session, audio_s3_key="audio/processing.mp3")
    await crud.update_job_status(
        db_session, processing_job.id, JobStatus.PROCESSING.value, assemblyai_id="proc-123"
    )

    # Create queued job
    await crud.create_job(db_session, audio_s3_key="audio/queued.mp3")

    jobs = await crud.get_all_processing_jobs(db_session)
    assert len(jobs) == 1
    assert jobs[0].id == processing_job.id


@pytest.mark.asyncio
async def test_get_all_processing_jobs_ignores_no_assemblyai_id(db_session: AsyncSession):
    """Test get_all_processing_jobs ignores jobs without AssemblyAI ID."""
    # Create processing job WITH assemblyai_id
    good_job = await crud.create_job(db_session, audio_s3_key="audio/good.mp3")
    await crud.update_job_status(
        db_session, good_job.id, JobStatus.PROCESSING.value, assemblyai_id="good-123"
    )

    # Create processing job WITHOUT assemblyai_id
    bad_job = await crud.create_job(db_session, audio_s3_key="audio/bad.mp3")
    await crud.update_job_status(db_session, bad_job.id, JobStatus.PROCESSING.value)

    jobs = await crud.get_all_processing_jobs(db_session)
    assert len(jobs) == 1
    assert jobs[0].id == good_job.id
