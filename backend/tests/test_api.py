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


async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_get_drive_empty(client):
    resp = await client.get("/api/drive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "empty"


async def test_list_jobs_empty(client):
    resp = await client.get("/api/jobs")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_job_and_get(client, app):
    jm = app.state.job_manager
    job = await jm.create_job(disc_info={"title_count": 1, "main_title": 1, "duration": 100.0})

    resp = await client.get(f"/api/jobs/{job.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == job.id


async def test_get_job_not_found(client):
    resp = await client.get("/api/jobs/nonexistent")
    assert resp.status_code == 404


async def test_delete_job(client, app):
    jm = app.state.job_manager
    job = await jm.create_job(disc_info={"title_count": 1, "main_title": 1, "duration": 100.0})

    resp = await client.delete(f"/api/jobs/{job.id}")
    assert resp.status_code == 200

    resp = await client.get(f"/api/jobs/{job.id}")
    assert resp.status_code == 404


async def test_get_settings(client):
    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "output_path" in data
    assert "auto_eject" in data


async def test_update_settings(client):
    resp = await client.put("/api/settings", json={"auto_eject": False})
    assert resp.status_code == 200

    resp = await client.get("/api/settings")
    assert resp.json()["auto_eject"] is False
