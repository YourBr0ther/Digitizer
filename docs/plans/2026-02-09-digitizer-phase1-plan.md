# Digitizer Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a fully functional DVD-to-MP4 ripping platform with auto-detection, web UI, and k3s deployment.

**Architecture:** Python/FastAPI backend handles DVD drive polling, FFmpeg remuxing, and job tracking via SQLite. Next.js frontend provides real-time dashboard via WebSocket. Both containerized and deployed to k3s with USB device passthrough and NFS storage.

**Tech Stack:** Python 3.12, FastAPI, aiosqlite, FFmpeg, lsdvd | Next.js 14 (App Router), Tailwind CSS | Docker, k3s

**Reference:** `docs/plans/2026-02-09-digitizer-design.md`

---

## Task 1: Backend Project Scaffolding

**Files:**
- Create: `backend/digitizer/__init__.py`
- Create: `backend/digitizer/config.py`
- Create: `backend/requirements.txt`
- Create: `backend/pyproject.toml`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

**Step 1: Create directory structure**

```
backend/
  digitizer/
    __init__.py
    config.py
  tests/
    __init__.py
    conftest.py
  requirements.txt
  pyproject.toml
```

**Step 2: Write `backend/requirements.txt`**

```
fastapi==0.115.*
uvicorn[standard]==0.34.*
aiosqlite==0.21.*
pydantic==2.*
pydantic-settings==2.*
python-dotenv==1.*
pytest==8.*
pytest-asyncio==0.25.*
httpx==0.28.*
```

**Step 3: Write `backend/pyproject.toml`**

```toml
[project]
name = "digitizer-backend"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 4: Write `backend/digitizer/config.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    output_base_path: str = "/output/dvd"
    naming_pattern: str = "YYYY-MM-DD_rip_NNN"
    auto_eject: bool = True
    drive_device: str = "/dev/sr0"
    poll_interval: float = 2.0
    db_path: str = "/data/digitizer.db"

    model_config = {"env_prefix": "DIGITIZER_"}


settings = Settings()
```

**Step 5: Write `backend/tests/conftest.py`**

```python
import os
import tempfile

import pytest


@pytest.fixture
def tmp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def tmp_output_dir(tmp_path):
    out = tmp_path / "output" / "dvd"
    out.mkdir(parents=True)
    return str(out)
```

**Step 6: Write `backend/digitizer/__init__.py`**

```python
```

**Step 7: Write `backend/tests/__init__.py`**

```python
```

**Step 8: Install dependencies and verify**

Run: `cd backend && pip install -r requirements.txt`
Expected: All packages install successfully

Run: `cd backend && python -m pytest tests/ -v`
Expected: "no tests ran" (0 collected), exit code 5 (no tests yet)

**Step 9: Commit**

```bash
git add backend/
git commit -m "feat: scaffold backend project with config and test setup"
```

---

## Task 2: Backend Database Layer

**Files:**
- Create: `backend/digitizer/db.py`
- Create: `backend/tests/test_db.py`

**Step 1: Write the failing test `backend/tests/test_db.py`**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_db.py -v`
Expected: FAIL - cannot import `digitizer.db`

**Step 3: Write `backend/digitizer/db.py`**

```python
import json

import aiosqlite


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def init(self):
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL DEFAULT 'dvd',
                disc_info TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'detected',
                progress INTEGER NOT NULL DEFAULT 0,
                output_path TEXT,
                file_size INTEGER,
                started_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT,
                error TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT OR IGNORE INTO settings (key, value) VALUES ('output_path', '/output/dvd');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('naming_pattern', 'YYYY-MM-DD_rip_NNN');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_eject', 'true');
            """
        )
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def create_job(
        self, job_id: str, source_type: str, disc_info: dict, output_path: str | None = None
    ):
        await self._conn.execute(
            "INSERT INTO jobs (id, source_type, disc_info, output_path) VALUES (?, ?, ?, ?)",
            (job_id, source_type, json.dumps(disc_info), output_path),
        )
        await self._conn.commit()

    async def get_job(self, job_id: str) -> dict | None:
        cursor = await self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        job = dict(row)
        job["disc_info"] = json.loads(job["disc_info"])
        return job

    async def list_jobs(self, limit: int = 10, offset: int = 0) -> list[dict]:
        cursor = await self._conn.execute(
            "SELECT * FROM jobs ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        jobs = []
        for row in rows:
            job = dict(row)
            job["disc_info"] = json.loads(job["disc_info"])
            jobs.append(job)
        return jobs

    async def update_job(self, job_id: str, **kwargs):
        allowed = {"status", "progress", "output_path", "file_size", "completed_at", "error"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [job_id]
        await self._conn.execute(
            f"UPDATE jobs SET {set_clause} WHERE id = ?", values
        )
        await self._conn.commit()

    async def delete_job(self, job_id: str) -> bool:
        cursor = await self._conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        await self._conn.commit()
        return cursor.rowcount > 0

    async def get_settings(self) -> dict:
        cursor = await self._conn.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        result = {}
        for row in rows:
            val = row["value"]
            if val in ("true", "false"):
                val = val == "true"
            result[row["key"]] = val
        return result

    async def update_settings(self, **kwargs):
        for key, value in kwargs.items():
            if isinstance(value, bool):
                value = "true" if value else "false"
            await self._conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )
        await self._conn.commit()

    async def get_next_sequence(self, date_str: str) -> int:
        cursor = await self._conn.execute(
            "SELECT COUNT(*) as cnt FROM jobs WHERE output_path LIKE ?",
            (f"%{date_str}%",),
        )
        row = await cursor.fetchone()
        return row["cnt"] + 1
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_db.py -v`
Expected: All 9 tests PASS

**Step 5: Commit**

```bash
git add backend/digitizer/db.py backend/tests/test_db.py
git commit -m "feat: add SQLite database layer with jobs and settings"
```

---

## Task 3: Backend Job Manager & Models

**Files:**
- Create: `backend/digitizer/models.py`
- Create: `backend/digitizer/jobs.py`
- Create: `backend/tests/test_jobs.py`

**Step 1: Write `backend/digitizer/models.py`** (Pydantic models, no tests needed - pure data)

```python
from enum import Enum

from pydantic import BaseModel


class JobStatus(str, Enum):
    DETECTED = "detected"
    RIPPING = "ripping"
    COMPLETE = "complete"
    FAILED = "failed"


class DriveStatus(str, Enum):
    EMPTY = "empty"
    DISC_DETECTED = "disc_detected"
    RIPPING = "ripping"


class DiscInfo(BaseModel):
    title_count: int = 0
    main_title: int = 1
    duration: float = 0.0


class Job(BaseModel):
    id: str
    source_type: str = "dvd"
    disc_info: DiscInfo = DiscInfo()
    status: JobStatus = JobStatus.DETECTED
    progress: int = 0
    output_path: str | None = None
    file_size: int | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None


class Settings(BaseModel):
    output_path: str = "/output/dvd"
    naming_pattern: str = "YYYY-MM-DD_rip_NNN"
    auto_eject: bool = True


class WSEvent(BaseModel):
    event: str
    data: dict
```

**Step 2: Write the failing test `backend/tests/test_jobs.py`**

```python
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
```

**Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_jobs.py -v`
Expected: FAIL - cannot import `digitizer.jobs`

**Step 4: Write `backend/digitizer/jobs.py`**

```python
import uuid
from datetime import datetime, timezone

from digitizer.db import Database
from digitizer.models import Job, JobStatus, DiscInfo


class JobManager:
    def __init__(self, db: Database, output_base: str = "/output/dvd"):
        self.db = db
        self.output_base = output_base

    async def create_job(self, disc_info: dict) -> Job:
        job_id = str(uuid.uuid4())
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        seq = await self.db.get_next_sequence(today)
        output_path = f"{self.output_base}/{today}_rip_{seq:03d}.mp4"

        await self.db.create_job(
            job_id=job_id,
            source_type="dvd",
            disc_info=disc_info,
            output_path=output_path,
        )
        row = await self.db.get_job(job_id)
        return self._row_to_job(row)

    async def get_job(self, job_id: str) -> Job | None:
        row = await self.db.get_job(job_id)
        if row is None:
            return None
        return self._row_to_job(row)

    async def list_jobs(self, limit: int = 10, offset: int = 0) -> list[Job]:
        rows = await self.db.list_jobs(limit=limit, offset=offset)
        return [self._row_to_job(r) for r in rows]

    async def mark_ripping(self, job_id: str) -> Job:
        await self.db.update_job(job_id, status="ripping")
        return await self.get_job(job_id)

    async def update_progress(self, job_id: str, progress: int) -> Job:
        await self.db.update_job(job_id, progress=min(progress, 100))
        return await self.get_job(job_id)

    async def mark_complete(self, job_id: str, file_size: int) -> Job:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.update_job(
            job_id,
            status="complete",
            progress=100,
            file_size=file_size,
            completed_at=now,
        )
        return await self.get_job(job_id)

    async def mark_failed(self, job_id: str, error: str) -> Job:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.update_job(
            job_id, status="failed", error=error, completed_at=now
        )
        return await self.get_job(job_id)

    async def delete_job(self, job_id: str) -> bool:
        return await self.db.delete_job(job_id)

    def _row_to_job(self, row: dict) -> Job:
        disc_info = row.get("disc_info", {})
        if isinstance(disc_info, str):
            import json
            disc_info = json.loads(disc_info)
        return Job(
            id=row["id"],
            source_type=row["source_type"],
            disc_info=DiscInfo(**disc_info) if disc_info else DiscInfo(),
            status=row["status"],
            progress=row["progress"],
            output_path=row.get("output_path"),
            file_size=row.get("file_size"),
            started_at=row.get("started_at"),
            completed_at=row.get("completed_at"),
            error=row.get("error"),
        )
```

**Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_jobs.py -v`
Expected: All 6 tests PASS

**Step 6: Commit**

```bash
git add backend/digitizer/models.py backend/digitizer/jobs.py backend/tests/test_jobs.py
git commit -m "feat: add job manager with lifecycle methods and Pydantic models"
```

---

## Task 4: Backend WebSocket Manager

**Files:**
- Create: `backend/digitizer/ws.py`
- Create: `backend/tests/test_ws.py`

**Step 1: Write the failing test `backend/tests/test_ws.py`**

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from digitizer.ws import ConnectionManager


@pytest.fixture
def manager():
    return ConnectionManager()


async def test_connect_adds_client(manager):
    ws = AsyncMock()
    await manager.connect(ws)
    assert len(manager.active_connections) == 1


async def test_disconnect_removes_client(manager):
    ws = AsyncMock()
    await manager.connect(ws)
    manager.disconnect(ws)
    assert len(manager.active_connections) == 0


async def test_broadcast_sends_to_all(manager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await manager.connect(ws1)
    await manager.connect(ws2)
    await manager.broadcast({"event": "test", "data": {}})
    ws1.send_json.assert_called_once_with({"event": "test", "data": {}})
    ws2.send_json.assert_called_once_with({"event": "test", "data": {}})


async def test_broadcast_removes_dead_connections(manager):
    ws_alive = AsyncMock()
    ws_dead = AsyncMock()
    ws_dead.send_json.side_effect = Exception("connection closed")
    await manager.connect(ws_alive)
    await manager.connect(ws_dead)
    await manager.broadcast({"event": "test", "data": {}})
    assert len(manager.active_connections) == 1
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_ws.py -v`
Expected: FAIL - cannot import `digitizer.ws`

**Step 3: Write `backend/digitizer/ws.py`**

```python
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_ws.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add backend/digitizer/ws.py backend/tests/test_ws.py
git commit -m "feat: add WebSocket connection manager with broadcast"
```

---

## Task 5: Backend DVD Ripper

**Files:**
- Create: `backend/digitizer/ripper.py`
- Create: `backend/tests/test_ripper.py`

**Step 1: Write the failing test `backend/tests/test_ripper.py`**

```python
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from digitizer.ripper import DVDRipper


@pytest.fixture
def ripper():
    return DVDRipper(drive_device="/dev/sr0")


def test_build_ffmpeg_command(ripper):
    cmd = ripper.build_ffmpeg_command(
        title_number=1,
        output_path="/output/dvd/2026-02-09_rip_001.mp4",
    )
    assert "ffmpeg" in cmd[0]
    assert "-i" in cmd
    assert "/output/dvd/2026-02-09_rip_001.mp4" in cmd
    # remux flags - copy, no transcode
    assert "-c" in cmd or "-codec" in cmd
    assert "copy" in cmd


def test_parse_progress_line(ripper):
    line = "frame=  100 fps=30.0 q=-1.0 size=   51200kB time=00:01:30.00 bitrate=4652.8kbits/s speed=2.0x"
    seconds = ripper.parse_time_from_progress(line)
    assert seconds == 90.0


def test_parse_progress_line_no_time(ripper):
    line = "Some random ffmpeg output"
    seconds = ripper.parse_time_from_progress(line)
    assert seconds is None


def test_calculate_progress_percent(ripper):
    pct = ripper.calculate_progress(current_seconds=45.0, total_seconds=90.0)
    assert pct == 50

    pct = ripper.calculate_progress(current_seconds=90.0, total_seconds=90.0)
    assert pct == 100

    pct = ripper.calculate_progress(current_seconds=0.0, total_seconds=90.0)
    assert pct == 0


@patch("digitizer.ripper.asyncio.create_subprocess_exec")
async def test_rip_calls_ffmpeg(mock_exec, ripper):
    mock_proc = AsyncMock()
    mock_proc.stderr.__aiter__ = AsyncMock(return_value=iter([]))
    mock_proc.wait = AsyncMock(return_value=0)
    mock_proc.returncode = 0
    mock_exec.return_value = mock_proc

    progress_cb = AsyncMock()
    result = await ripper.rip(
        title_number=1,
        duration=100.0,
        output_path="/tmp/test.mp4",
        on_progress=progress_cb,
    )
    assert result is True
    mock_exec.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_ripper.py -v`
Expected: FAIL - cannot import `digitizer.ripper`

**Step 3: Write `backend/digitizer/ripper.py`**

```python
import asyncio
import logging
import os
import re
from collections.abc import Callable, Awaitable

logger = logging.getLogger(__name__)

TIME_PATTERN = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")


class DVDRipper:
    def __init__(self, drive_device: str = "/dev/sr0"):
        self.drive_device = drive_device

    def build_ffmpeg_command(
        self, title_number: int, output_path: str
    ) -> list[str]:
        # dvdbackup + ffmpeg approach: read VOBs via concat protocol
        # For home-burned DVDs, the simplest approach is reading the device directly
        input_path = f"dvd://{title_number}//{self.drive_device}"
        return [
            "ffmpeg",
            "-y",
            "-hwaccel", "auto",
            "-i", input_path,
            "-c", "copy",
            "-movflags", "+faststart",
            output_path,
        ]

    def parse_time_from_progress(self, line: str) -> float | None:
        match = TIME_PATTERN.search(line)
        if not match:
            return None
        h, m, s, cs = match.groups()
        return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100

    def calculate_progress(self, current_seconds: float, total_seconds: float) -> int:
        if total_seconds <= 0:
            return 0
        return min(int((current_seconds / total_seconds) * 100), 100)

    async def rip(
        self,
        title_number: int,
        duration: float,
        output_path: str,
        on_progress: Callable[[int], Awaitable[None]] | None = None,
    ) -> bool:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = self.build_ffmpeg_command(title_number, output_path)
        logger.info("Running: %s", " ".join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )

        async for raw_line in proc.stderr:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            seconds = self.parse_time_from_progress(line)
            if seconds is not None and on_progress:
                pct = self.calculate_progress(seconds, duration)
                await on_progress(pct)

        await proc.wait()
        success = proc.returncode == 0
        if not success:
            logger.error("FFmpeg exited with code %d", proc.returncode)
        return success

    async def eject(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "eject", self.drive_device,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except Exception:
            logger.exception("Failed to eject disc")
            return False
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_ripper.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add backend/digitizer/ripper.py backend/tests/test_ripper.py
git commit -m "feat: add DVD ripper with FFmpeg remux and progress parsing"
```

---

## Task 6: Backend Drive Monitor

**Files:**
- Create: `backend/digitizer/drive_monitor.py`
- Create: `backend/tests/test_drive_monitor.py`

**Step 1: Write the failing test `backend/tests/test_drive_monitor.py`**

```python
import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from digitizer.drive_monitor import DriveMonitor
from digitizer.models import DriveStatus


@pytest.fixture
def monitor():
    return DriveMonitor(device="/dev/sr0")


def test_initial_status_is_empty(monitor):
    assert monitor.status == DriveStatus.EMPTY


LSDVD_OUTPUT = """Disc Title: UNKNOWN
Title: 01, Length: 01:30:00.000 Chapters: 01, Cells: 01, Audio streams: 01, Subpictures: 00
Longest track: 01
"""


@patch("digitizer.drive_monitor.asyncio.create_subprocess_exec")
async def test_check_disc_detected(mock_exec, monitor):
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(LSDVD_OUTPUT.encode(), b""))
    mock_proc.returncode = 0
    mock_exec.return_value = mock_proc

    result = await monitor.check_disc()
    assert result is not None
    assert result["main_title"] == 1
    assert result["duration"] == 5400.0


@patch("digitizer.drive_monitor.asyncio.create_subprocess_exec")
async def test_check_disc_empty(mock_exec, monitor):
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))
    mock_proc.returncode = 1
    mock_exec.return_value = mock_proc

    result = await monitor.check_disc()
    assert result is None


def test_parse_lsdvd_output(monitor):
    info = monitor.parse_lsdvd(LSDVD_OUTPUT)
    assert info["title_count"] == 1
    assert info["main_title"] == 1
    assert info["duration"] == 5400.0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_drive_monitor.py -v`
Expected: FAIL - cannot import `digitizer.drive_monitor`

**Step 3: Write `backend/digitizer/drive_monitor.py`**

```python
import asyncio
import logging
import re

from digitizer.models import DriveStatus

logger = logging.getLogger(__name__)

TITLE_PATTERN = re.compile(
    r"Title:\s*(\d+),\s*Length:\s*(\d{2}):(\d{2}):(\d{2})"
)
LONGEST_PATTERN = re.compile(r"Longest track:\s*(\d+)")


class DriveMonitor:
    def __init__(self, device: str = "/dev/sr0"):
        self.device = device
        self.status = DriveStatus.EMPTY
        self._disc_present = False

    async def check_disc(self) -> dict | None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "lsdvd", self.device,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                return None
            return self.parse_lsdvd(stdout.decode("utf-8", errors="replace"))
        except Exception:
            logger.exception("Error checking disc")
            return None

    def parse_lsdvd(self, output: str) -> dict:
        titles = []
        for match in TITLE_PATTERN.finditer(output):
            num = int(match.group(1))
            h, m, s = int(match.group(2)), int(match.group(3)), int(match.group(4))
            duration = h * 3600 + m * 60 + s
            titles.append({"number": num, "duration": float(duration)})

        longest_match = LONGEST_PATTERN.search(output)
        main_title = int(longest_match.group(1)) if longest_match else (
            max(titles, key=lambda t: t["duration"])["number"] if titles else 1
        )

        main_duration = next(
            (t["duration"] for t in titles if t["number"] == main_title), 0.0
        )

        return {
            "title_count": len(titles),
            "main_title": main_title,
            "duration": main_duration,
        }

    async def poll_once(self) -> tuple[DriveStatus, dict | None]:
        disc_info = await self.check_disc()
        old_status = self.status

        if disc_info is not None and not self._disc_present:
            self._disc_present = True
            self.status = DriveStatus.DISC_DETECTED
            return self.status, disc_info
        elif disc_info is None and self._disc_present:
            self._disc_present = False
            self.status = DriveStatus.EMPTY
            return self.status, None

        return old_status, None

    def set_ripping(self):
        self.status = DriveStatus.RIPPING

    def set_empty(self):
        self.status = DriveStatus.EMPTY
        self._disc_present = False
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_drive_monitor.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add backend/digitizer/drive_monitor.py backend/tests/test_drive_monitor.py
git commit -m "feat: add drive monitor with lsdvd parsing and disc detection"
```

---

## Task 7: Backend API Routes & Main App

**Files:**
- Create: `backend/digitizer/api.py`
- Create: `backend/digitizer/main.py`
- Create: `backend/tests/test_api.py`

**Step 1: Write the failing test `backend/tests/test_api.py`**

```python
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
    # Manually create a job via the job manager
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_api.py -v`
Expected: FAIL - cannot import

**Step 3: Write `backend/digitizer/api.py`**

```python
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/drive")
async def get_drive(request: Request):
    monitor = request.app.state.drive_monitor
    return {"status": monitor.status.value}


@router.get("/jobs")
async def list_jobs(request: Request, limit: int = 10, offset: int = 0):
    jm = request.app.state.job_manager
    jobs = await jm.list_jobs(limit=limit, offset=offset)
    return [j.model_dump() for j in jobs]


@router.get("/jobs/{job_id}")
async def get_job(request: Request, job_id: str):
    jm = request.app.state.job_manager
    job = await jm.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump()


@router.delete("/jobs/{job_id}")
async def delete_job(request: Request, job_id: str):
    jm = request.app.state.job_manager
    deleted = await jm.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"deleted": True}


@router.get("/settings")
async def get_settings(request: Request):
    db = request.app.state.db
    return await db.get_settings()


@router.put("/settings")
async def update_settings(request: Request):
    db = request.app.state.db
    body = await request.json()
    await db.update_settings(**body)
    return await db.get_settings()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, request: Request = None):
    manager = websocket.app.state.ws_manager
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

**Step 4: Write `backend/digitizer/main.py`**

```python
import asyncio
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from digitizer.api import router
from digitizer.db import Database
from digitizer.drive_monitor import DriveMonitor
from digitizer.jobs import JobManager
from digitizer.ripper import DVDRipper
from digitizer.ws import ConnectionManager

logger = logging.getLogger(__name__)


async def create_app(
    db_path: str | None = None,
    output_base: str | None = None,
    start_monitor: bool = True,
) -> FastAPI:
    app = FastAPI(title="Digitizer", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    _db_path = db_path or os.environ.get("DIGITIZER_DB_PATH", "/data/digitizer.db")
    _output_base = output_base or os.environ.get("DIGITIZER_OUTPUT_BASE_PATH", "/output/dvd")
    _device = os.environ.get("DIGITIZER_DRIVE_DEVICE", "/dev/sr0")

    db = Database(_db_path)
    await db.init()

    ws_manager = ConnectionManager()
    drive_monitor = DriveMonitor(device=_device)
    ripper = DVDRipper(drive_device=_device)
    job_manager = JobManager(db=db, output_base=_output_base)

    app.state.db = db
    app.state.ws_manager = ws_manager
    app.state.drive_monitor = drive_monitor
    app.state.ripper = ripper
    app.state.job_manager = job_manager

    if start_monitor:
        app.state.monitor_task = asyncio.create_task(
            _monitor_loop(app)
        )

    return app


async def _monitor_loop(app: FastAPI):
    monitor = app.state.drive_monitor
    ws = app.state.ws_manager
    jm = app.state.job_manager
    ripper = app.state.ripper
    poll_interval = float(os.environ.get("DIGITIZER_POLL_INTERVAL", "2.0"))
    auto_eject = True

    while True:
        try:
            status, disc_info = await monitor.poll_once()

            if disc_info is not None and status.value == "disc_detected":
                await ws.broadcast({"event": "drive_status", "data": {"status": "disc_detected"}})

                job = await jm.create_job(disc_info=disc_info)
                monitor.set_ripping()
                await ws.broadcast({"event": "drive_status", "data": {"status": "ripping"}})

                await jm.mark_ripping(job.id)
                await ws.broadcast({
                    "event": "job_progress",
                    "data": {"job_id": job.id, "progress": 0},
                })

                async def on_progress(pct: int):
                    await jm.update_progress(job.id, pct)
                    await ws.broadcast({
                        "event": "job_progress",
                        "data": {"job_id": job.id, "progress": pct},
                    })

                success = await ripper.rip(
                    title_number=disc_info["main_title"],
                    duration=disc_info["duration"],
                    output_path=job.output_path,
                    on_progress=on_progress,
                )

                if success:
                    file_size = os.path.getsize(job.output_path) if os.path.exists(job.output_path) else 0
                    completed = await jm.mark_complete(job.id, file_size=file_size)
                    await ws.broadcast({
                        "event": "job_complete",
                        "data": completed.model_dump(),
                    })

                    settings = await app.state.db.get_settings()
                    if settings.get("auto_eject", True):
                        await ripper.eject()
                        monitor.set_empty()
                else:
                    failed = await jm.mark_failed(job.id, error="FFmpeg rip failed")
                    await ws.broadcast({
                        "event": "job_failed",
                        "data": failed.model_dump(),
                    })

                monitor.set_empty()
                await ws.broadcast({"event": "drive_status", "data": {"status": "empty"}})

        except Exception:
            logger.exception("Error in monitor loop")

        await asyncio.sleep(poll_interval)


# For uvicorn entry point
app: FastAPI | None = None


async def startup():
    global app
    app = await create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("digitizer.main:app", host="0.0.0.0", port=8000, factory=True)
```

> **Note:** The uvicorn factory pattern needs a small wrapper. Update the CMD in Dockerfile and the entrypoint accordingly. For now, tests use `create_app()` directly.

**Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_api.py -v`
Expected: All 8 tests PASS

**Step 6: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All 22 tests PASS (9 db + 6 jobs + 4 ws + 5 ripper + 4 monitor + 8 api... minus overlaps = all pass)

**Step 7: Commit**

```bash
git add backend/digitizer/api.py backend/digitizer/main.py backend/tests/test_api.py
git commit -m "feat: add FastAPI routes, WebSocket endpoint, and main app with monitor loop"
```

---

## Task 8: Frontend — Next.js App with Dashboard

**Files:**
- Create: `frontend/` - entire Next.js project

> **REQUIRED:** Use the `frontend-design` skill to build this task. The frontend should be a dark-themed, utility/control-panel aesthetic with:
>
> **Pages to build:**
> 1. **Dashboard `/`** - Drive status card (No Disc / Disc Detected / Ripping with progress bar), active job with progress + elapsed time, recent 10 jobs list with status badges
> 2. **Job History `/jobs`** - Paginated table: date, filename, source type, duration, file size, status. Clickable rows.
> 3. **Job Detail `/jobs/[id]`** - Full metadata, output path, error log if failed
> 4. **Settings `/settings`** - Output path, naming format, auto-eject toggle
>
> **Shared layout:** Sidebar nav with links to Dashboard, Jobs, Settings. App name "Digitizer" in header.
>
> **WebSocket hook `useDigitizerSocket`:**
> - Connect to `WS {BACKEND_URL}/api/ws` on mount
> - Parse events: `drive_status`, `job_progress`, `job_complete`, `job_failed`
> - Store in React context, auto-reconnect on disconnect
>
> **API client:**
> - `GET /api/drive`, `GET /api/jobs`, `GET /api/jobs/{id}`, `DELETE /api/jobs/{id}`
> - `GET /api/settings`, `PUT /api/settings`
> - Base URL from `NEXT_PUBLIC_API_URL` env var (default `http://localhost:8000`)
>
> **Tech:** Next.js 14 App Router, Tailwind CSS, TypeScript. No component libraries — hand-rolled with Tailwind.
>
> **After building:** Run `npm run build` to verify it compiles.

**Commit after frontend is built:**

```bash
git add frontend/
git commit -m "feat: add Next.js frontend with dashboard, jobs, settings, and WebSocket"
```

---

## Task 9: Dockerfiles

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `docker-compose.dev.yml` (for local testing)

**Step 1: Write `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg lsdvd dvdbackup eject \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY digitizer/ digitizer/

RUN mkdir -p /data /output/dvd

CMD ["uvicorn", "digitizer.main:app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
```

**Step 2: Write `frontend/Dockerfile`**

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
```

**Step 3: Write `docker-compose.dev.yml`** (local dev/test only)

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
      - ./output:/output
    devices:
      - "/dev/sr0:/dev/sr0"
    privileged: true
    environment:
      - DIGITIZER_DB_PATH=/data/digitizer.db
      - DIGITIZER_OUTPUT_BASE_PATH=/output/dvd
      - DIGITIZER_DRIVE_DEVICE=/dev/sr0

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on:
      - backend
```

**Step 4: Commit**

```bash
git add backend/Dockerfile frontend/Dockerfile docker-compose.dev.yml
git commit -m "feat: add Dockerfiles and docker-compose for local dev"
```

---

## Task 10: k3s Manifests

**Files:**
- Create: `k8s/namespace.yaml`
- Create: `k8s/backend-deployment.yaml`
- Create: `k8s/frontend-deployment.yaml`
- Create: `k8s/services.yaml`
- Create: `k8s/ingress.yaml`
- Create: `k8s/storage.yaml`

**Step 1: Write `k8s/namespace.yaml`**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: digitizer
```

**Step 2: Write `k8s/storage.yaml`**

```yaml
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: digitizer-db
  namespace: digitizer
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path
  resources:
    requests:
      storage: 1Gi
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: digitizer-nfs
spec:
  capacity:
    storage: 500Gi
  accessModes:
    - ReadWriteMany
  nfs:
    server: "NFS_SERVER_IP"   # <-- CHANGE THIS
    path: "/export/digitizer"  # <-- CHANGE THIS
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: digitizer-output
  namespace: digitizer
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: ""
  volumeName: digitizer-nfs
  resources:
    requests:
      storage: 500Gi
```

**Step 3: Write `k8s/backend-deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: digitizer-backend
  namespace: digitizer
spec:
  replicas: 1
  selector:
    matchLabels:
      app: digitizer-backend
  template:
    metadata:
      labels:
        app: digitizer-backend
    spec:
      nodeSelector:
        digitizer/dvd-drive: "true"
      containers:
        - name: backend
          image: digitizer-backend:latest
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8000
          securityContext:
            privileged: true
          env:
            - name: DIGITIZER_DB_PATH
              value: /data/digitizer.db
            - name: DIGITIZER_OUTPUT_BASE_PATH
              value: /output/dvd
            - name: DIGITIZER_DRIVE_DEVICE
              value: /dev/sr0
          volumeMounts:
            - name: data
              mountPath: /data
            - name: output
              mountPath: /output
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: digitizer-db
        - name: output
          persistentVolumeClaim:
            claimName: digitizer-output
```

**Step 4: Write `k8s/frontend-deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: digitizer-frontend
  namespace: digitizer
spec:
  replicas: 1
  selector:
    matchLabels:
      app: digitizer-frontend
  template:
    metadata:
      labels:
        app: digitizer-frontend
    spec:
      containers:
        - name: frontend
          image: digitizer-frontend:latest
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 3000
          env:
            - name: NEXT_PUBLIC_API_URL
              value: http://digitizer-backend:8000
```

**Step 5: Write `k8s/services.yaml`**

```yaml
---
apiVersion: v1
kind: Service
metadata:
  name: digitizer-backend
  namespace: digitizer
spec:
  selector:
    app: digitizer-backend
  ports:
    - port: 8000
      targetPort: 8000
---
apiVersion: v1
kind: Service
metadata:
  name: digitizer-frontend
  namespace: digitizer
spec:
  selector:
    app: digitizer-frontend
  ports:
    - port: 3000
      targetPort: 3000
```

**Step 6: Write `k8s/ingress.yaml`**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: digitizer
  namespace: digitizer
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-http-version: "1.1"
    nginx.ingress.kubernetes.io/configuration-snippet: |
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection "upgrade";
spec:
  ingressClassName: nginx
  rules:
    - host: digitizer.local  # <-- CHANGE THIS to your domain/IP
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: digitizer-backend
                port:
                  number: 8000
          - path: /
            pathType: Prefix
            backend:
              service:
                name: digitizer-frontend
                port:
                  number: 3000
```

**Step 7: Commit**

```bash
git add k8s/
git commit -m "feat: add k3s deployment manifests with NFS and device passthrough"
```

---

## Parallel Work Assignment (for teams)

These tasks can be parallelized across agents:

| Agent | Tasks | Skills |
|-------|-------|--------|
| **backend** | Tasks 1-7 (sequential) | TDD, Python |
| **frontend** | Task 8 | `frontend-design` skill |
| **devops** | Tasks 9-10 (after backend+frontend scaffolds exist) | Docker, k8s |

**Dependencies:**
- Tasks 1-7 are sequential (each builds on prior)
- Task 8 (frontend) is independent — can run in parallel with backend tasks
- Task 9 (Dockerfiles) depends on Tasks 7 and 8 being complete
- Task 10 (k8s) depends on Task 9
