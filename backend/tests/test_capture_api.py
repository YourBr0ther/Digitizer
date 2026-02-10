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


async def test_capture_status_idle(client):
    resp = await client.get("/api/capture/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "idle"
    assert data["job_id"] is None


async def test_capture_stop_not_recording(client):
    resp = await client.post("/api/capture/stop")
    assert resp.status_code == 409


async def test_capture_start_creates_job(client, app):
    # Mock the capture to not actually start FFmpeg
    from unittest.mock import AsyncMock, patch
    with patch.object(app.state.vhs_capture, "start", new_callable=AsyncMock) as mock_start:
        mock_start.return_value = True
        resp = await client.post("/api/capture/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_type"] == "vhs"
        assert data["status"] == "ripping"
        assert "job_id" in data


async def test_capture_start_conflict(client, app):
    app.state.vhs_capture._recording = True
    resp = await client.post("/api/capture/start")
    assert resp.status_code == 409
    app.state.vhs_capture._recording = False


async def test_jobs_list_includes_vhs(client, app):
    jm = app.state.job_manager
    await jm.create_job(disc_info={"title_count": 0, "main_title": 0, "duration": 0}, source_type="vhs")
    resp = await client.get("/api/jobs")
    assert resp.status_code == 200
    jobs = resp.json()
    assert any(j["source_type"] == "vhs" for j in jobs)


async def test_jobs_filter_by_source_type(client, app):
    jm = app.state.job_manager
    await jm.create_job(disc_info={"title_count": 1, "main_title": 1, "duration": 100}, source_type="dvd")
    await jm.create_job(disc_info={"title_count": 0, "main_title": 0, "duration": 0}, source_type="vhs")

    resp = await client.get("/api/jobs?source_type=vhs")
    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) >= 1
    assert all(j["source_type"] == "vhs" for j in jobs)

    resp = await client.get("/api/jobs?source_type=dvd")
    assert resp.status_code == 200
    jobs = resp.json()
    assert all(j["source_type"] == "dvd" for j in jobs)
