import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from digitizer.main import create_app


@pytest.fixture
async def app(tmp_db_path, tmp_output_dir):
    application = await create_app(
        db_path=tmp_db_path, output_base=tmp_output_dir, start_monitor=False
    )
    yield application
    await application.state.db.close()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def vhs_job(app):
    """Create a completed VHS job for testing."""
    jm = app.state.job_manager
    job = await jm.create_job(
        disc_info={"title_count": 0, "main_title": 0, "duration": 300.0},
        source_type="vhs",
    )
    await jm.mark_complete(job.id, file_size=100_000_000)
    return job


async def test_analyze_requires_complete_vhs_job(client, app):
    jm = app.state.job_manager
    # Create a DVD job (not VHS)
    job = await jm.create_job(disc_info={"title_count": 1, "main_title": 1, "duration": 100})
    resp = await client.post(f"/api/jobs/{job.id}/analyze")
    assert resp.status_code == 400


async def test_analyze_starts_detection(client, vhs_job, app):
    with patch.object(app.state.scene_detector, "analyze", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = [
            {"id": "s1", "scene_index": 1, "start_time": 0.0, "end_time": 60.0, "duration": 60.0, "thumbnail_path": "/t/1.jpg"},
            {"id": "s2", "scene_index": 2, "start_time": 60.0, "end_time": 300.0, "duration": 240.0, "thumbnail_path": "/t/2.jpg"},
        ]
        resp = await client.post(f"/api/jobs/{vhs_job.id}/analyze")
        assert resp.status_code == 202

        # Wait a moment for the background task to complete
        import asyncio
        await asyncio.sleep(0.5)

        # Check scenes were stored
        resp = await client.get(f"/api/jobs/{vhs_job.id}/scenes")
        assert resp.status_code == 200
        scenes = resp.json()
        assert len(scenes) == 2


async def test_get_scenes_empty(client, vhs_job):
    resp = await client.get(f"/api/jobs/{vhs_job.id}/scenes")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_scenes_not_found(client):
    resp = await client.get("/api/jobs/nonexistent/scenes")
    assert resp.status_code == 404


async def test_update_scenes(client, vhs_job, app):
    # First create some scenes via DB
    db = app.state.db
    await db.create_scene(
        scene_id="s1", job_id=vhs_job.id, scene_index=1,
        start_time=0.0, end_time=60.0, duration=60.0
    )

    # Update with new scene list
    new_scenes = [
        {"scene_index": 1, "start_time": 0.0, "end_time": 45.0},
        {"scene_index": 2, "start_time": 45.0, "end_time": 300.0},
    ]
    resp = await client.put(f"/api/jobs/{vhs_job.id}/scenes", json=new_scenes)
    assert resp.status_code == 200

    resp = await client.get(f"/api/jobs/{vhs_job.id}/scenes")
    scenes = resp.json()
    assert len(scenes) == 2
    assert scenes[0]["end_time"] == 45.0


async def test_split_scenes(client, vhs_job, app):
    db = app.state.db
    await db.create_scene(
        scene_id="s1", job_id=vhs_job.id, scene_index=1,
        start_time=0.0, end_time=150.0, duration=150.0,
    )
    await db.create_scene(
        scene_id="s2", job_id=vhs_job.id, scene_index=2,
        start_time=150.0, end_time=300.0, duration=150.0,
    )

    with patch.object(app.state.splitter, "split_all", new_callable=AsyncMock) as mock_split:
        mock_split.return_value = ["/output/scene_001.mp4", "/output/scene_002.mp4"]
        resp = await client.post(f"/api/jobs/{vhs_job.id}/split")
        assert resp.status_code == 202
