import uuid

import pytest

from digitizer.db import Database


@pytest.fixture
async def db(tmp_db_path):
    database = Database(tmp_db_path)
    await database.init()
    yield database
    await database.close()


async def test_create_and_list_scenes(db):
    job_id = str(uuid.uuid4())
    await db.create_job(job_id=job_id, source_type="vhs", disc_info={})

    scene_id = str(uuid.uuid4())
    await db.create_scene(
        scene_id=scene_id,
        job_id=job_id,
        scene_index=1,
        start_time=0.0,
        end_time=45.2,
        duration=45.2,
        thumbnail_path="/thumbs/test/scene_001.jpg",
    )
    scenes = await db.list_scenes(job_id)
    assert len(scenes) == 1
    assert scenes[0]["scene_index"] == 1
    assert scenes[0]["start_time"] == 0.0
    assert scenes[0]["end_time"] == 45.2


async def test_replace_scenes(db):
    job_id = str(uuid.uuid4())
    await db.create_job(job_id=job_id, source_type="vhs", disc_info={})

    # Create initial scenes
    for i in range(3):
        await db.create_scene(
            scene_id=str(uuid.uuid4()),
            job_id=job_id,
            scene_index=i + 1,
            start_time=float(i * 30),
            end_time=float((i + 1) * 30),
            duration=30.0,
        )
    scenes = await db.list_scenes(job_id)
    assert len(scenes) == 3

    # Replace with new scenes
    await db.delete_scenes_for_job(job_id)
    await db.create_scene(
        scene_id=str(uuid.uuid4()),
        job_id=job_id,
        scene_index=1,
        start_time=0.0,
        end_time=90.0,
        duration=90.0,
    )
    scenes = await db.list_scenes(job_id)
    assert len(scenes) == 1


async def test_update_scene_split_path(db):
    job_id = str(uuid.uuid4())
    await db.create_job(job_id=job_id, source_type="vhs", disc_info={})

    scene_id = str(uuid.uuid4())
    await db.create_scene(
        scene_id=scene_id,
        job_id=job_id,
        scene_index=1,
        start_time=0.0,
        end_time=30.0,
        duration=30.0,
    )
    await db.update_scene(scene_id, split_path="/output/vhs/scenes/test/scene_001.mp4")
    scenes = await db.list_scenes(job_id)
    assert scenes[0]["split_path"] == "/output/vhs/scenes/test/scene_001.mp4"


async def test_job_analysis_status(db):
    job_id = str(uuid.uuid4())
    await db.create_job(job_id=job_id, source_type="vhs", disc_info={})

    await db.update_job(job_id, analysis_status="analyzing")
    job = await db.get_job(job_id)
    assert job["analysis_status"] == "analyzing"

    await db.update_job(job_id, analysis_status="analyzed", scene_count=5)
    job = await db.get_job(job_id)
    assert job["analysis_status"] == "analyzed"
    assert job["scene_count"] == 5
