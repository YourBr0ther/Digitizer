import uuid
from unittest.mock import AsyncMock

import pytest

from digitizer.jobs import JobManager
from digitizer.db import Database
from digitizer.models import JobStatus


@pytest.fixture
async def db(tmp_db_path):
    database = Database(tmp_db_path)
    await database.init()
    yield database
    await database.close()


@pytest.fixture
def job_manager(db, tmp_output_dir):
    return JobManager(db=db, output_base=tmp_output_dir)


async def test_create_job(job_manager):
    disc_info = {"title_count": 1, "main_title": 1, "duration": 3600.0}
    job = await job_manager.create_job(disc_info=disc_info)
    assert job.status == JobStatus.DETECTED
    assert job.source_type == "dvd"
    assert job.disc_info.duration == 3600.0


async def test_create_job_generates_output_path(job_manager):
    disc_info = {"title_count": 1, "main_title": 1, "duration": 3600.0}
    job = await job_manager.create_job(disc_info=disc_info)
    assert job.output_path is not None
    assert job.output_path.endswith(".mp4")
    assert "_rip_001" in job.output_path


async def test_mark_ripping(job_manager):
    disc_info = {"title_count": 1, "main_title": 1, "duration": 100.0}
    job = await job_manager.create_job(disc_info=disc_info)
    updated = await job_manager.mark_ripping(job.id)
    assert updated.status == JobStatus.RIPPING


async def test_update_progress(job_manager):
    disc_info = {"title_count": 1, "main_title": 1, "duration": 100.0}
    job = await job_manager.create_job(disc_info=disc_info)
    updated = await job_manager.update_progress(job.id, 42)
    assert updated.progress == 42


async def test_mark_complete(job_manager):
    disc_info = {"title_count": 1, "main_title": 1, "duration": 100.0}
    job = await job_manager.create_job(disc_info=disc_info)
    updated = await job_manager.mark_complete(job.id, file_size=1_000_000)
    assert updated.status == JobStatus.COMPLETE
    assert updated.file_size == 1_000_000
    assert updated.completed_at is not None


async def test_mark_failed(job_manager):
    disc_info = {"title_count": 1, "main_title": 1, "duration": 100.0}
    job = await job_manager.create_job(disc_info=disc_info)
    updated = await job_manager.mark_failed(job.id, error="FFmpeg crashed")
    assert updated.status == JobStatus.FAILED
    assert updated.error == "FFmpeg crashed"
