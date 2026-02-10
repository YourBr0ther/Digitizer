# Digitizer Phase 2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add real-time HDMI/VHS capture to the Digitizer platform with manual start/stop from the web UI.

**Architecture:** New capture module alongside existing DVD ripper. FFmpeg reads from V4L2 device, encodes H.264/AAC in real-time. Manual start/stop via REST API. Progress via WebSocket.

**Tech Stack:** Same as Phase 1 - Python 3.12, FastAPI, FFmpeg, Next.js 14, Tailwind CSS

**Reference:** `docs/plans/2026-02-09-digitizer-phase2-design.md`

---

## Task 1: Backend - Update Config and Models for VHS Capture

**Files:**
- Modify: `backend/digitizer/config.py`
- Modify: `backend/digitizer/models.py`
- Modify: `backend/digitizer/db.py`

**Step 1: Update `backend/digitizer/config.py`**

Add new fields to Settings class:

```python
class Settings(BaseSettings):
    output_base_path: str = "/output/dvd"
    vhs_output_path: str = "/output/vhs"
    naming_pattern: str = "YYYY-MM-DD_rip_NNN"
    auto_eject: bool = True
    drive_device: str = "/dev/sr0"
    capture_device: str = "/dev/video0"
    poll_interval: float = 2.0
    db_path: str = "/data/digitizer.db"
    encoding_preset: str = "fast"
    crf_quality: int = 23
    audio_bitrate: str = "192k"

    model_config = {"env_prefix": "DIGITIZER_"}
```

**Step 2: Update `backend/digitizer/models.py`**

Add CaptureStatus enum:

```python
class CaptureStatus(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
```

**Step 3: Update `backend/digitizer/db.py`**

Add new default settings rows in `init()` method - add these INSERT OR IGNORE lines:

```python
INSERT OR IGNORE INTO settings (key, value) VALUES ('vhs_output_path', '/output/vhs');
INSERT OR IGNORE INTO settings (key, value) VALUES ('encoding_preset', 'fast');
INSERT OR IGNORE INTO settings (key, value) VALUES ('crf_quality', '23');
INSERT OR IGNORE INTO settings (key, value) VALUES ('audio_bitrate', '192k');
```

**Step 4: Run existing tests to verify nothing broke**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All 36 existing tests PASS

**Step 5: Commit**

```bash
git add backend/digitizer/config.py backend/digitizer/models.py backend/digitizer/db.py
git commit -m "feat: add VHS capture config fields, CaptureStatus model, and new DB settings"
```

---

## Task 2: Backend - VHS Capture Module

**Files:**
- Create: `backend/digitizer/capture.py`
- Create: `backend/tests/test_capture.py`

**Step 1: Write the failing test `backend/tests/test_capture.py`**

```python
import asyncio
import signal
from unittest.mock import AsyncMock, patch, MagicMock, PropertyMock

import pytest

from digitizer.capture import VHSCapture


@pytest.fixture
def capture():
    return VHSCapture(
        capture_device="/dev/video0",
        encoding_preset="fast",
        crf_quality=23,
        audio_bitrate="192k",
    )


def test_initial_state_is_idle(capture):
    assert capture.is_recording is False
    assert capture.current_process is None


def test_build_ffmpeg_command(capture):
    cmd = capture.build_ffmpeg_command(output_path="/output/vhs/test.mp4")
    assert "ffmpeg" in cmd[0]
    assert "-f" in cmd
    assert "v4l2" in cmd
    assert "/dev/video0" in cmd
    assert "-c:v" in cmd
    assert "libx264" in cmd
    assert "-preset" in cmd
    assert "fast" in cmd
    assert "-crf" in cmd
    assert "23" in cmd
    assert "-c:a" in cmd
    assert "aac" in cmd
    assert "/output/vhs/test.mp4" in cmd


def test_build_ffmpeg_command_custom_preset(capture):
    capture.encoding_preset = "medium"
    capture.crf_quality = 20
    cmd = capture.build_ffmpeg_command(output_path="/output/vhs/test.mp4")
    assert "medium" in cmd
    assert "20" in cmd


def test_parse_elapsed_time(capture):
    line = "frame=  100 fps=30.0 q=28.0 size=   5120kB time=00:05:30.00 bitrate=1234.5kbits/s speed=1.0x"
    seconds = capture.parse_elapsed_time(line)
    assert seconds == 330.0


def test_parse_elapsed_time_no_match(capture):
    line = "Some random output"
    seconds = capture.parse_elapsed_time(line)
    assert seconds is None


@patch("digitizer.capture.asyncio.create_subprocess_exec")
async def test_start_recording(mock_exec, capture):
    mock_proc = AsyncMock()
    mock_proc.pid = 12345
    mock_proc.stderr = AsyncMock()
    # Mock the async iterator to just complete immediately
    mock_proc.stderr.__aiter__ = lambda self: self
    mock_proc.stderr.__anext__ = AsyncMock(side_effect=StopAsyncIteration)
    mock_proc.wait = AsyncMock(return_value=0)
    mock_proc.returncode = 0
    mock_exec.return_value = mock_proc

    progress_cb = AsyncMock()
    result = await capture.start(
        output_path="/tmp/test.mp4",
        on_progress=progress_cb,
    )
    assert result is True
    mock_exec.assert_called_once()


async def test_start_while_recording_raises(capture):
    capture._recording = True
    with pytest.raises(RuntimeError, match="Already recording"):
        await capture.start(output_path="/tmp/test.mp4")


@patch("digitizer.capture.asyncio.create_subprocess_exec")
async def test_stop_recording(mock_exec, capture):
    mock_proc = AsyncMock()
    mock_proc.pid = 12345
    mock_proc.send_signal = MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mock_proc.returncode = 0

    capture._recording = True
    capture._process = mock_proc

    await capture.stop()
    mock_proc.send_signal.assert_called_once_with(signal.SIGINT)
    assert capture._recording is False


async def test_stop_while_not_recording_raises(capture):
    with pytest.raises(RuntimeError, match="Not recording"):
        await capture.stop()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_capture.py -v`
Expected: FAIL - cannot import `digitizer.capture`

**Step 3: Write `backend/digitizer/capture.py`**

```python
import asyncio
import logging
import os
import re
import signal
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

TIME_PATTERN = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")


class VHSCapture:
    def __init__(
        self,
        capture_device: str = "/dev/video0",
        encoding_preset: str = "fast",
        crf_quality: int = 23,
        audio_bitrate: str = "192k",
    ):
        self.capture_device = capture_device
        self.encoding_preset = encoding_preset
        self.crf_quality = crf_quality
        self.audio_bitrate = audio_bitrate
        self._recording = False
        self._process: asyncio.subprocess.Process | None = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def current_process(self) -> asyncio.subprocess.Process | None:
        return self._process

    def build_ffmpeg_command(self, output_path: str) -> list[str]:
        return [
            "ffmpeg",
            "-y",
            "-f", "v4l2",
            "-i", self.capture_device,
            "-c:v", "libx264",
            "-preset", self.encoding_preset,
            "-crf", str(self.crf_quality),
            "-c:a", "aac",
            "-b:a", self.audio_bitrate,
            "-movflags", "+faststart",
            output_path,
        ]

    def parse_elapsed_time(self, line: str) -> float | None:
        match = TIME_PATTERN.search(line)
        if not match:
            return None
        h, m, s, cs = match.groups()
        return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100

    async def start(
        self,
        output_path: str,
        on_progress: Callable[[float, int], Awaitable[None]] | None = None,
    ) -> bool:
        if self._recording:
            raise RuntimeError("Already recording")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = self.build_ffmpeg_command(output_path)
        logger.info("Starting capture: %s", " ".join(cmd))

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        self._recording = True

        try:
            async for raw_line in self._process.stderr:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                elapsed = self.parse_elapsed_time(line)
                if elapsed is not None and on_progress:
                    file_size = 0
                    if os.path.exists(output_path):
                        try:
                            file_size = os.path.getsize(output_path)
                        except OSError:
                            pass
                    await on_progress(elapsed, file_size)

            await self._process.wait()
            success = self._process.returncode == 0 or self._process.returncode == -2  # SIGINT
            return success
        finally:
            self._recording = False
            self._process = None

    async def stop(self):
        if not self._recording or self._process is None:
            raise RuntimeError("Not recording")

        logger.info("Stopping capture (SIGINT to pid %d)", self._process.pid)
        self._process.send_signal(signal.SIGINT)
        await self._process.wait()
        self._recording = False
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_capture.py -v`
Expected: All 8 tests PASS

**Step 5: Commit**

```bash
git add backend/digitizer/capture.py backend/tests/test_capture.py
git commit -m "feat: add VHS capture module with FFmpeg V4L2 recording and SIGINT stop"
```

---

## Task 3: Backend - Capture API Routes

**Files:**
- Modify: `backend/digitizer/api.py`
- Modify: `backend/digitizer/main.py`
- Create: `backend/tests/test_capture_api.py`

**Step 1: Write the failing test `backend/tests/test_capture_api.py`**

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


async def test_capture_status_idle(client):
    resp = await client.get("/api/capture/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "idle"
    assert data["job_id"] is None


async def test_capture_stop_not_recording(client):
    resp = await client.post("/api/capture/stop")
    assert resp.status_code == 404


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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_capture_api.py -v`
Expected: FAIL

**Step 3: Update `backend/digitizer/jobs.py`**

Add `source_type` parameter to `create_job`:

```python
async def create_job(self, disc_info: dict, source_type: str = "dvd") -> Job:
    job_id = str(uuid.uuid4())
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    seq = await self.db.get_next_sequence(today)
    if source_type == "vhs":
        output_path = f"{self.vhs_output_base}/{today}_capture_{seq:03d}.mp4"
    else:
        output_path = f"{self.output_base}/{today}_rip_{seq:03d}.mp4"

    await self.db.create_job(
        job_id=job_id,
        source_type=source_type,
        disc_info=disc_info,
        output_path=output_path,
    )
    row = await self.db.get_job(job_id)
    return self._row_to_job(row)
```

Also update `__init__` to accept `vhs_output_base`:

```python
def __init__(self, db: Database, output_base: str = "/output/dvd", vhs_output_base: str = "/output/vhs"):
    self.db = db
    self.output_base = output_base
    self.vhs_output_base = vhs_output_base
```

Add `list_jobs` with optional source_type filter. Update `db.py` to support filtered listing:

In `db.py`, add method:
```python
async def list_jobs(self, limit: int = 10, offset: int = 0, source_type: str | None = None) -> list[dict]:
    if source_type:
        cursor = await self._conn.execute(
            "SELECT * FROM jobs WHERE source_type = ? ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (source_type, limit, offset),
        )
    else:
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
```

Update `jobs.py` `list_jobs` to pass through:
```python
async def list_jobs(self, limit: int = 10, offset: int = 0, source_type: str | None = None) -> list[Job]:
    rows = await self.db.list_jobs(limit=limit, offset=offset, source_type=source_type)
    return [self._row_to_job(r) for r in rows]
```

**Step 4: Add capture routes to `backend/digitizer/api.py`**

Add these routes:

```python
@router.get("/capture/status")
async def capture_status(request: Request):
    vhs = request.app.state.vhs_capture
    return {
        "status": "recording" if vhs.is_recording else "idle",
        "job_id": getattr(request.app.state, "_capture_job_id", None),
    }


@router.post("/capture/start")
async def capture_start(request: Request):
    vhs = request.app.state.vhs_capture
    if vhs.is_recording:
        raise HTTPException(status_code=409, detail="Already recording")

    jm = request.app.state.job_manager
    ws = request.app.state.ws_manager

    job = await jm.create_job(
        disc_info={"title_count": 0, "main_title": 0, "duration": 0},
        source_type="vhs",
    )
    await jm.mark_ripping(job.id)
    request.app.state._capture_job_id = job.id

    await ws.broadcast({"event": "capture_status", "data": {"status": "recording"}})

    async def on_progress(elapsed: float, file_size: int):
        await ws.broadcast({
            "event": "job_progress",
            "data": {"job_id": job.id, "elapsed": elapsed, "file_size": file_size},
        })

    async def run_capture():
        try:
            success = await vhs.start(
                output_path=job.output_path,
                on_progress=on_progress,
            )
            if success:
                final_size = 0
                import os
                if os.path.exists(job.output_path):
                    final_size = os.path.getsize(job.output_path)
                completed = await jm.mark_complete(job.id, file_size=final_size)
                await ws.broadcast({"event": "job_complete", "data": completed.model_dump()})
            else:
                failed = await jm.mark_failed(job.id, error="Capture failed")
                await ws.broadcast({"event": "job_failed", "data": failed.model_dump()})
        except Exception as e:
            failed = await jm.mark_failed(job.id, error=str(e))
            await ws.broadcast({"event": "job_failed", "data": failed.model_dump()})
        finally:
            request.app.state._capture_job_id = None
            await ws.broadcast({"event": "capture_status", "data": {"status": "idle"}})

    import asyncio
    asyncio.create_task(run_capture())

    return {"job_id": job.id, "source_type": "vhs", "status": "ripping", "output_path": job.output_path}


@router.post("/capture/stop")
async def capture_stop(request: Request):
    vhs = request.app.state.vhs_capture
    if not vhs.is_recording:
        raise HTTPException(status_code=404, detail="Not recording")

    await vhs.stop()
    job_id = request.app.state._capture_job_id
    if job_id:
        jm = request.app.state.job_manager
        job = await jm.get_job(job_id)
        if job:
            return job.model_dump()
    return {"status": "stopped"}
```

Update the `list_jobs` route to support source_type filter:

```python
@router.get("/jobs")
async def list_jobs(request: Request, limit: int = 10, offset: int = 0, source_type: str | None = None):
    jm = request.app.state.job_manager
    jobs = await jm.list_jobs(limit=limit, offset=offset, source_type=source_type)
    return [j.model_dump() for j in jobs]
```

**Step 5: Update `backend/digitizer/main.py`**

Add VHS capture initialization in `create_app`:

```python
from digitizer.capture import VHSCapture

# Inside create_app, after existing initialization:
_capture_device = os.environ.get("DIGITIZER_CAPTURE_DEVICE", "/dev/video0")
_vhs_output = os.environ.get("DIGITIZER_VHS_OUTPUT_PATH", "/output/vhs")

vhs_capture = VHSCapture(
    capture_device=_capture_device,
    encoding_preset=os.environ.get("DIGITIZER_ENCODING_PRESET", "fast"),
    crf_quality=int(os.environ.get("DIGITIZER_CRF_QUALITY", "23")),
    audio_bitrate=os.environ.get("DIGITIZER_AUDIO_BITRATE", "192k"),
)

# Update job_manager to include vhs_output_base
job_manager = JobManager(db=db, output_base=_output_base, vhs_output_base=_vhs_output)

app.state.vhs_capture = vhs_capture
app.state._capture_job_id = None
```

**Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_capture_api.py -v`
Expected: All 6 tests PASS

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS (existing + new)

**Step 7: Commit**

```bash
git add backend/digitizer/api.py backend/digitizer/main.py backend/digitizer/jobs.py backend/digitizer/db.py backend/tests/test_capture_api.py
git commit -m "feat: add capture API routes with start/stop/status and source_type filtering"
```

---

## Task 4: Frontend - VHS Capture Card Component

**Files:**
- Create: `frontend/src/components/vhs-capture-card.tsx`
- Modify: `frontend/src/app/page.tsx` (dashboard)
- Modify: `frontend/src/context/digitizer-context.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`

> **REQUIRED:** Use the `frontend-design` skill to build this task.

**What to build:**

1. **Update `types.ts`** - Add CaptureStatus type, capture API response types

2. **Update `api.ts`** - Add three new functions:
   - `getCaptureStatus()` → GET /api/capture/status
   - `startCapture()` → POST /api/capture/start
   - `stopCapture()` → POST /api/capture/stop
   - Update `getJobs()` to accept optional `source_type` filter param

3. **Update `digitizer-context.tsx`** - Add capture state:
   - `captureStatus: "idle" | "recording"`
   - `captureJobId: string | null`
   - `captureElapsed: number` (seconds)
   - `captureFileSize: number` (bytes)
   - Handle `capture_status` WebSocket event
   - Handle `job_progress` events where source is VHS (update elapsed/fileSize)

4. **Create `vhs-capture-card.tsx`** - New component matching the control-panel aesthetic:
   - **Idle state:** "Ready to Capture" heading, large green "Start Capture" button, subtle equipment-ready indicator
   - **Recording state:** Red pulsing recording dot + "RECORDING" text, elapsed time counter (HH:MM:SS counting up), file size display (updating in real-time), red "Stop Capture" button
   - Same card styling as the existing drive-status-card but with VHS/tape branding

5. **Update Dashboard `page.tsx`** - Two-panel layout:
   - Left column: existing DriveStatusCard + ActiveJobPanel (for DVD)
   - Right column: new VHSCaptureCard
   - Below both: RecentJobs (shows both DVD and VHS jobs)
   - Responsive: side-by-side on desktop, stacked on mobile

**Commit:**

```bash
git add frontend/
git commit -m "feat: add VHS capture card with start/stop controls and real-time progress"
```

---

## Task 5: Frontend - Job History Filter and Settings Updates

**Files:**
- Modify: `frontend/src/app/jobs/page.tsx`
- Modify: `frontend/src/app/settings/page.tsx`

> **REQUIRED:** Use the `frontend-design` skill to build this task.

**What to build:**

1. **Job History page** - Add source type filter:
   - Dropdown/tab bar at top: "All" | "DVD" | "VHS"
   - Passes `?source_type=dvd` or `?source_type=vhs` to API
   - "All" passes no filter
   - VHS jobs show a different badge color (purple) vs DVD (blue)

2. **Settings page** - Add VHS Encoding section:
   - Section header: "VHS Capture Settings"
   - VHS output path text input (default: /output/vhs)
   - Encoding preset selector: dropdown with "fast" / "medium" / "slow"
   - CRF quality slider: range 18-28, default 23, with label showing current value and description (18=highest quality/largest, 28=lowest/smallest)
   - Audio bitrate selector: dropdown with "128k" / "192k" / "256k"
   - Save button saves all settings via PUT /api/settings

**Commit:**

```bash
git add frontend/
git commit -m "feat: add source type filter to job history and VHS encoding settings"
```

---

## Task 6: Backend/DevOps - Update Deployment for Capture Device

**Files:**
- Modify: `k8s/backend-deployment.yaml`
- Modify: `docker-compose.dev.yml`

**Step 1: Update `k8s/backend-deployment.yaml`**

Add new env vars to the backend container:

```yaml
- name: DIGITIZER_CAPTURE_DEVICE
  value: /dev/video0
- name: DIGITIZER_VHS_OUTPUT_PATH
  value: /output/vhs
- name: DIGITIZER_ENCODING_PRESET
  value: fast
- name: DIGITIZER_CRF_QUALITY
  value: "23"
- name: DIGITIZER_AUDIO_BITRATE
  value: 192k
```

**Step 2: Update `docker-compose.dev.yml`**

Add to backend service:

```yaml
environment:
  - DIGITIZER_DB_PATH=/data/digitizer.db
  - DIGITIZER_OUTPUT_BASE_PATH=/output/dvd
  - DIGITIZER_DRIVE_DEVICE=/dev/sr0
  - DIGITIZER_CAPTURE_DEVICE=/dev/video0
  - DIGITIZER_VHS_OUTPUT_PATH=/output/vhs
  - DIGITIZER_ENCODING_PRESET=fast
  - DIGITIZER_CRF_QUALITY=23
  - DIGITIZER_AUDIO_BITRATE=192k
devices:
  - "/dev/sr0:/dev/sr0"
  - "/dev/video0:/dev/video0"
```

**Step 3: Commit**

```bash
git add k8s/backend-deployment.yaml docker-compose.dev.yml
git commit -m "feat: add capture device passthrough and VHS env vars to deployment"
```

---

## Parallel Work Assignment (for teams)

| Agent | Tasks | Skills |
|-------|-------|--------|
| **backend** | Tasks 1-3 (sequential: config → capture module → API routes) | TDD, Python |
| **frontend** | Tasks 4-5 (sequential: capture card → history filter + settings) | `frontend-design` skill |
| **devops** | Task 6 (after backend task 3 is done) | k8s, Docker |

**Dependencies:**
- Tasks 1-3 are sequential (each builds on prior)
- Tasks 4-5 are independent from backend — can run in parallel
- Task 6 depends on Task 3 being complete (needs to know the env vars)
