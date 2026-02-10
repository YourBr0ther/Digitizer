import uuid
from datetime import datetime, timezone

import pytest

from digitizer.db import Database


@pytest.fixture
async def db(tmp_db_path):
    database = Database(tmp_db_path)
    await database.init()
    yield database
    await database.close()


async def test_init_creates_tables(db):
    jobs = await db.list_jobs(limit=10, offset=0)
    assert jobs == []


async def test_create_and_get_job(db):
    job_id = str(uuid.uuid4())
    await db.create_job(
        job_id=job_id,
        source_type="dvd",
        disc_info={"title_count": 1, "main_title": 1, "duration": 3600.0},
    )
    job = await db.get_job(job_id)
    assert job is not None
    assert job["id"] == job_id
    assert job["source_type"] == "dvd"
    assert job["status"] == "detected"
    assert job["progress"] == 0


async def test_update_job_status(db):
    job_id = str(uuid.uuid4())
    await db.create_job(job_id=job_id, source_type="dvd", disc_info={})
    await db.update_job(job_id, status="ripping", progress=50)
    job = await db.get_job(job_id)
    assert job["status"] == "ripping"
    assert job["progress"] == 50


async def test_complete_job(db):
    job_id = str(uuid.uuid4())
    await db.create_job(job_id=job_id, source_type="dvd", disc_info={})
    await db.update_job(
        job_id,
        status="complete",
        progress=100,
        output_path="/output/dvd/2026-02-09_rip_001.mp4",
        file_size=4_000_000_000,
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    job = await db.get_job(job_id)
    assert job["status"] == "complete"
    assert job["file_size"] == 4_000_000_000


async def test_list_jobs_pagination(db):
    for i in range(15):
        await db.create_job(
            job_id=str(uuid.uuid4()), source_type="dvd", disc_info={}
        )
    page1 = await db.list_jobs(limit=10, offset=0)
    page2 = await db.list_jobs(limit=10, offset=10)
    assert len(page1) == 10
    assert len(page2) == 5


async def test_delete_job(db):
    job_id = str(uuid.uuid4())
    await db.create_job(job_id=job_id, source_type="dvd", disc_info={})
    deleted = await db.delete_job(job_id)
    assert deleted is True
    job = await db.get_job(job_id)
    assert job is None


async def test_get_settings_defaults(db):
    s = await db.get_settings()
    assert s["output_path"] == "/output/dvd"
    assert s["auto_eject"] is True


async def test_update_settings(db):
    await db.update_settings(output_path="/mnt/nas/dvds", auto_eject=False)
    s = await db.get_settings()
    assert s["output_path"] == "/mnt/nas/dvds"
    assert s["auto_eject"] is False


async def test_get_next_sequence_number(db):
    seq = await db.get_next_sequence("2026-02-09")
    assert seq == 1
    await db.create_job(
        job_id=str(uuid.uuid4()),
        source_type="dvd",
        disc_info={},
        output_path="/output/dvd/2026-02-09_rip_001.mp4",
    )
    seq = await db.get_next_sequence("2026-02-09")
    assert seq == 2
