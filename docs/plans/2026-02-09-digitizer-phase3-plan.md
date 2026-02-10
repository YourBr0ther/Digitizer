# Digitizer Phase 3 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add AI-powered scene detection and video splitting to VHS captures, with a review UI for adjusting cut points.

**Architecture:** PySceneDetect analyzes completed VHS captures, FFmpeg splits at detected cuts. New scenes DB table, 5 API routes, scene review page with timeline visualization.

**Tech Stack:** Python 3.12, PySceneDetect, OpenCV, FFmpeg | Next.js 14, Tailwind CSS

**Reference:** `docs/plans/2026-02-09-digitizer-phase3-design.md`

---

## Task 1: Backend - Database Schema Updates

**Files:**
- Modify: `backend/digitizer/db.py`
- Modify: `backend/digitizer/models.py`
- Create: `backend/tests/test_scenes_db.py`

**Step 1: Update `backend/digitizer/models.py`**

Add new models:

```python
class AnalysisStatus(str, Enum):
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    SPLITTING = "splitting"
    SPLIT_COMPLETE = "split_complete"


class Scene(BaseModel):
    id: str
    job_id: str
    scene_index: int
    start_time: float
    end_time: float
    duration: float
    thumbnail_path: str | None = None
    split_path: str | None = None
    created_at: str | None = None
```

Add `analysis_status` and `scene_count` optional fields to the existing `Job` model:

```python
class Job(BaseModel):
    # ... existing fields ...
    analysis_status: str | None = None
    scene_count: int | None = None
```

**Step 2: Write the failing test `backend/tests/test_scenes_db.py`**

```python
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
```

**Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_scenes_db.py -v`
Expected: FAIL

**Step 4: Update `backend/digitizer/db.py`**

Add to the `init()` method's CREATE TABLE block:

```sql
CREATE TABLE IF NOT EXISTS scenes (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    scene_index INTEGER NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    duration REAL NOT NULL,
    thumbnail_path TEXT,
    split_path TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Add `analysis_status` and `scene_count` columns to jobs table. Use a migration-safe approach since the table may already exist:

```python
# After CREATE TABLE statements in init():
# Add columns if they don't exist (safe for existing DBs)
try:
    await self._conn.execute("ALTER TABLE jobs ADD COLUMN analysis_status TEXT")
except Exception:
    pass  # Column already exists
try:
    await self._conn.execute("ALTER TABLE jobs ADD COLUMN scene_count INTEGER")
except Exception:
    pass  # Column already exists
await self._conn.commit()
```

Add `analysis_status` and `scene_count` to the `allowed` set in `update_job()`:

```python
allowed = {"status", "progress", "output_path", "file_size", "completed_at", "error", "analysis_status", "scene_count"}
```

Add new methods:

```python
async def create_scene(
    self, scene_id: str, job_id: str, scene_index: int,
    start_time: float, end_time: float, duration: float,
    thumbnail_path: str | None = None, split_path: str | None = None,
):
    await self._conn.execute(
        """INSERT INTO scenes (id, job_id, scene_index, start_time, end_time, duration, thumbnail_path, split_path)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (scene_id, job_id, scene_index, start_time, end_time, duration, thumbnail_path, split_path),
    )
    await self._conn.commit()

async def list_scenes(self, job_id: str) -> list[dict]:
    cursor = await self._conn.execute(
        "SELECT * FROM scenes WHERE job_id = ? ORDER BY scene_index", (job_id,)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]

async def delete_scenes_for_job(self, job_id: str):
    await self._conn.execute("DELETE FROM scenes WHERE job_id = ?", (job_id,))
    await self._conn.commit()

async def update_scene(self, scene_id: str, **kwargs):
    allowed = {"split_path", "thumbnail_path", "start_time", "end_time", "duration", "scene_index"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [scene_id]
    await self._conn.execute(f"UPDATE scenes SET {set_clause} WHERE id = ?", values)
    await self._conn.commit()
```

Also update `_row_to_job` in `jobs.py` to include the new fields.

**Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_scenes_db.py -v`
Expected: All 4 tests PASS

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS (existing + new)

**Step 6: Commit**

```bash
git add backend/digitizer/db.py backend/digitizer/models.py backend/digitizer/jobs.py backend/tests/test_scenes_db.py
git commit -m "feat: add scenes table, analysis_status to jobs, and scene DB methods"
```

---

## Task 2: Backend - Scene Detector Module

**Files:**
- Create: `backend/digitizer/scene_detector.py`
- Create: `backend/tests/test_scene_detector.py`
- Modify: `backend/requirements.txt`

**Step 1: Update `backend/requirements.txt`**

Add:
```
scenedetect[opencv]==0.6.*
opencv-python-headless==4.*
```

Install: `cd backend && pip install -r requirements.txt`

**Step 2: Write the failing test `backend/tests/test_scene_detector.py`**

```python
import os
import uuid
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from digitizer.scene_detector import SceneDetector


@pytest.fixture
def detector():
    return SceneDetector(
        content_threshold=22.0,
        fade_threshold=12,
        min_scene_length=5.0,
    )


def test_default_thresholds(detector):
    assert detector.content_threshold == 22.0
    assert detector.fade_threshold == 12
    assert detector.min_scene_length == 5.0


def test_filter_short_scenes(detector):
    """Scenes shorter than min_scene_length should be merged with adjacent."""
    raw_scenes = [
        (0.0, 45.0),      # normal scene
        (45.0, 46.5),      # 1.5s - static/noise, should be merged
        (46.5, 120.0),     # normal scene
        (120.0, 121.0),    # 1.0s - static, should be merged
        (121.0, 200.0),    # normal scene
    ]
    filtered = detector.filter_short_scenes(raw_scenes)
    assert len(filtered) == 3
    assert filtered[0] == (0.0, 46.5)   # merged with short scene
    assert filtered[1] == (46.5, 121.0)  # merged with short scene
    assert filtered[2] == (121.0, 200.0)


def test_filter_short_scenes_no_filtering_needed(detector):
    raw_scenes = [
        (0.0, 60.0),
        (60.0, 120.0),
        (120.0, 180.0),
    ]
    filtered = detector.filter_short_scenes(raw_scenes)
    assert len(filtered) == 3


def test_filter_short_scenes_single_scene(detector):
    raw_scenes = [(0.0, 300.0)]
    filtered = detector.filter_short_scenes(raw_scenes)
    assert len(filtered) == 1


def test_build_thumbnail_command(detector):
    cmd = detector.build_thumbnail_command(
        video_path="/input/video.mp4",
        timestamp=45.2,
        output_path="/thumbs/scene_001.jpg",
    )
    assert "ffmpeg" in cmd[0]
    assert "-ss" in cmd
    assert "45.2" in cmd or "45.200" in cmd
    assert "/thumbs/scene_001.jpg" in cmd


@patch("digitizer.scene_detector.open_video")
@patch("digitizer.scene_detector.SceneManager")
async def test_analyze_returns_scenes(mock_sm_cls, mock_open_video, detector, tmp_path):
    """Test that analyze calls PySceneDetect and returns scene list."""
    mock_video = MagicMock()
    mock_video.duration = MagicMock(return_value=180.0)
    mock_video.frame_rate = 29.97
    mock_open_video.return_value.__enter__ = MagicMock(return_value=mock_video)
    mock_open_video.return_value.__exit__ = MagicMock(return_value=False)

    mock_sm = MagicMock()
    mock_sm_cls.return_value = mock_sm
    # Simulate PySceneDetect returning scene boundaries
    mock_scene1 = MagicMock()
    mock_scene1.__getitem__ = lambda self, idx: [MagicMock(get_seconds=lambda: 0.0), MagicMock(get_seconds=lambda: 60.0)][idx]
    mock_scene2 = MagicMock()
    mock_scene2.__getitem__ = lambda self, idx: [MagicMock(get_seconds=lambda: 60.0), MagicMock(get_seconds=lambda: 180.0)][idx]
    mock_sm.get_scene_list.return_value = [mock_scene1, mock_scene2]

    thumb_dir = str(tmp_path / "thumbs")
    with patch.object(detector, "_extract_thumbnail", new_callable=AsyncMock) as mock_thumb:
        mock_thumb.return_value = True
        scenes = await detector.analyze(
            video_path="/input/video.mp4",
            thumbnail_dir=thumb_dir,
        )

    assert len(scenes) == 2
    assert scenes[0]["start_time"] == 0.0
    assert scenes[0]["end_time"] == 60.0
    assert scenes[1]["start_time"] == 60.0
    assert scenes[1]["end_time"] == 180.0
```

**Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_scene_detector.py -v`
Expected: FAIL - cannot import

**Step 4: Write `backend/digitizer/scene_detector.py`**

```python
import asyncio
import logging
import os
import uuid
from collections.abc import Awaitable, Callable

from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector, ThresholdDetector

logger = logging.getLogger(__name__)


class SceneDetector:
    def __init__(
        self,
        content_threshold: float = 22.0,
        fade_threshold: int = 12,
        min_scene_length: float = 5.0,
    ):
        self.content_threshold = content_threshold
        self.fade_threshold = fade_threshold
        self.min_scene_length = min_scene_length

    def filter_short_scenes(
        self, scenes: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        if len(scenes) <= 1:
            return scenes

        filtered = []
        i = 0
        while i < len(scenes):
            start, end = scenes[i]
            duration = end - start
            if duration < self.min_scene_length and filtered:
                # Merge short scene into previous
                prev_start, _ = filtered[-1]
                filtered[-1] = (prev_start, end)
            elif duration < self.min_scene_length and i + 1 < len(scenes):
                # Merge short scene into next
                next_start, next_end = scenes[i + 1]
                scenes[i + 1] = (start, next_end)
            else:
                filtered.append((start, end))
            i += 1
        return filtered

    def build_thumbnail_command(
        self, video_path: str, timestamp: float, output_path: str
    ) -> list[str]:
        return [
            "ffmpeg",
            "-y",
            "-ss", f"{timestamp:.3f}",
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            output_path,
        ]

    async def _extract_thumbnail(
        self, video_path: str, timestamp: float, output_path: str
    ) -> bool:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = self.build_thumbnail_command(video_path, timestamp, output_path)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0

    async def analyze(
        self,
        video_path: str,
        thumbnail_dir: str,
        on_progress: Callable[[int], Awaitable[None]] | None = None,
    ) -> list[dict]:
        if on_progress:
            await on_progress(0)

        # Run PySceneDetect (CPU-bound, run in thread)
        raw_scenes = await asyncio.to_thread(
            self._detect_scenes, video_path
        )

        if on_progress:
            await on_progress(50)

        # Filter short scenes (static/noise)
        filtered = self.filter_short_scenes(raw_scenes)

        # Extract thumbnails
        scenes = []
        for i, (start, end) in enumerate(filtered):
            scene_index = i + 1
            thumb_path = os.path.join(thumbnail_dir, f"scene_{scene_index:03d}.jpg")

            # Extract thumbnail at the start of each scene (offset by 0.5s for better frame)
            thumb_time = start + 0.5 if start + 0.5 < end else start
            await self._extract_thumbnail(video_path, thumb_time, thumb_path)

            scenes.append({
                "id": str(uuid.uuid4()),
                "scene_index": scene_index,
                "start_time": start,
                "end_time": end,
                "duration": round(end - start, 3),
                "thumbnail_path": thumb_path,
            })

            if on_progress:
                pct = 50 + int((scene_index / len(filtered)) * 50)
                await on_progress(min(pct, 100))

        return scenes

    def _detect_scenes(self, video_path: str) -> list[tuple[float, float]]:
        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=self.content_threshold))
        scene_manager.add_detector(ThresholdDetector(threshold=self.fade_threshold))
        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()

        if not scene_list:
            # No cuts detected - entire video is one scene
            duration = video.duration.get_seconds()
            return [(0.0, duration)]

        return [
            (scene[0].get_seconds(), scene[1].get_seconds())
            for scene in scene_list
        ]
```

**Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_scene_detector.py -v`
Expected: All 7 tests PASS

**Step 6: Commit**

```bash
git add backend/digitizer/scene_detector.py backend/tests/test_scene_detector.py backend/requirements.txt
git commit -m "feat: add scene detector with PySceneDetect, noise filtering, and thumbnails"
```

---

## Task 3: Backend - Video Splitter Module

**Files:**
- Create: `backend/digitizer/splitter.py`
- Create: `backend/tests/test_splitter.py`

**Step 1: Write the failing test `backend/tests/test_splitter.py`**

```python
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from digitizer.splitter import VideoSplitter


@pytest.fixture
def splitter():
    return VideoSplitter()


def test_build_split_command(splitter):
    cmd = splitter.build_split_command(
        input_path="/input/video.mp4",
        start_time=45.2,
        end_time=120.5,
        output_path="/output/scene_001.mp4",
    )
    assert "ffmpeg" in cmd[0]
    assert "-ss" in cmd
    assert "-to" in cmd or "-t" in cmd
    assert "-c" in cmd
    assert "copy" in cmd
    assert "/output/scene_001.mp4" in cmd


def test_build_split_command_from_start(splitter):
    cmd = splitter.build_split_command(
        input_path="/input/video.mp4",
        start_time=0.0,
        end_time=60.0,
        output_path="/output/scene_001.mp4",
    )
    assert "-ss" in cmd
    assert "0.000" in cmd or "0" in cmd


@patch("digitizer.splitter.asyncio.create_subprocess_exec")
async def test_split_single_scene(mock_exec, splitter):
    mock_proc = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mock_proc.returncode = 0
    mock_exec.return_value = mock_proc

    result = await splitter.split_scene(
        input_path="/input/video.mp4",
        start_time=0.0,
        end_time=60.0,
        output_path="/output/scene_001.mp4",
    )
    assert result is True


@patch("digitizer.splitter.asyncio.create_subprocess_exec")
async def test_split_all(mock_exec, splitter, tmp_path):
    mock_proc = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mock_proc.returncode = 0
    mock_exec.return_value = mock_proc

    scenes = [
        {"scene_index": 1, "start_time": 0.0, "end_time": 60.0},
        {"scene_index": 2, "start_time": 60.0, "end_time": 120.0},
        {"scene_index": 3, "start_time": 120.0, "end_time": 180.0},
    ]
    progress_cb = AsyncMock()
    output_dir = str(tmp_path / "scenes")

    paths = await splitter.split_all(
        input_path="/input/video.mp4",
        scenes=scenes,
        output_dir=output_dir,
        on_progress=progress_cb,
    )
    assert len(paths) == 3
    assert all("scene_" in p for p in paths)
    assert progress_cb.call_count >= 3


@patch("digitizer.splitter.asyncio.create_subprocess_exec")
async def test_split_scene_failure(mock_exec, splitter):
    mock_proc = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=1)
    mock_proc.returncode = 1
    mock_exec.return_value = mock_proc

    result = await splitter.split_scene(
        input_path="/input/video.mp4",
        start_time=0.0,
        end_time=60.0,
        output_path="/output/scene_001.mp4",
    )
    assert result is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_splitter.py -v`
Expected: FAIL

**Step 3: Write `backend/digitizer/splitter.py`**

```python
import asyncio
import logging
import os
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class VideoSplitter:
    def build_split_command(
        self,
        input_path: str,
        start_time: float,
        end_time: float,
        output_path: str,
    ) -> list[str]:
        return [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-ss", f"{start_time:.3f}",
            "-to", f"{end_time:.3f}",
            "-c", "copy",
            "-movflags", "+faststart",
            output_path,
        ]

    async def split_scene(
        self,
        input_path: str,
        start_time: float,
        end_time: float,
        output_path: str,
    ) -> bool:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = self.build_split_command(input_path, start_time, end_time, output_path)
        logger.info("Splitting: %s", " ".join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0

    async def split_all(
        self,
        input_path: str,
        scenes: list[dict],
        output_dir: str,
        on_progress: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> list[str]:
        os.makedirs(output_dir, exist_ok=True)
        output_paths = []

        for i, scene in enumerate(scenes):
            idx = scene["scene_index"]
            output_path = os.path.join(output_dir, f"scene_{idx:03d}.mp4")

            success = await self.split_scene(
                input_path=input_path,
                start_time=scene["start_time"],
                end_time=scene["end_time"],
                output_path=output_path,
            )

            if success:
                output_paths.append(output_path)
            else:
                logger.error("Failed to split scene %d", idx)

            if on_progress:
                pct = int(((i + 1) / len(scenes)) * 100)
                await on_progress(pct, idx)

        return output_paths
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_splitter.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add backend/digitizer/splitter.py backend/tests/test_splitter.py
git commit -m "feat: add video splitter with FFmpeg segment copy"
```

---

## Task 4: Backend - Scene Analysis API Routes

**Files:**
- Modify: `backend/digitizer/api.py`
- Modify: `backend/digitizer/main.py`
- Create: `backend/tests/test_scenes_api.py`

**Step 1: Write the failing test `backend/tests/test_scenes_api.py`**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_scenes_api.py -v`
Expected: FAIL

**Step 3: Add routes to `backend/digitizer/api.py`**

```python
import asyncio
import uuid
import os

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

# ... existing routes ...

@router.post("/jobs/{job_id}/analyze", status_code=202)
async def analyze_scenes(request: Request, job_id: str):
    jm = request.app.state.job_manager
    db = request.app.state.db
    ws = request.app.state.ws_manager
    detector = request.app.state.scene_detector

    job = await jm.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.source_type != "vhs":
        raise HTTPException(status_code=400, detail="Scene analysis only available for VHS captures")
    if job.status.value != "complete":
        raise HTTPException(status_code=400, detail="Job must be complete before analysis")

    await db.update_job(job_id, analysis_status="analyzing")
    await ws.broadcast({"event": "analysis_progress", "data": {"job_id": job_id, "progress": 0}})

    async def run_analysis():
        try:
            thumb_dir = os.path.join(os.path.dirname(job.output_path), "thumbs", job_id)

            async def on_progress(pct: int):
                await ws.broadcast({"event": "analysis_progress", "data": {"job_id": job_id, "progress": pct}})

            scenes = await detector.analyze(
                video_path=job.output_path,
                thumbnail_dir=thumb_dir,
                on_progress=on_progress,
            )

            # Store scenes in DB
            await db.delete_scenes_for_job(job_id)
            for scene in scenes:
                await db.create_scene(
                    scene_id=scene.get("id", str(uuid.uuid4())),
                    job_id=job_id,
                    scene_index=scene["scene_index"],
                    start_time=scene["start_time"],
                    end_time=scene["end_time"],
                    duration=scene["duration"],
                    thumbnail_path=scene.get("thumbnail_path"),
                )

            await db.update_job(job_id, analysis_status="analyzed", scene_count=len(scenes))
            await ws.broadcast({"event": "analysis_complete", "data": {"job_id": job_id, "scene_count": len(scenes)}})

        except Exception as e:
            await db.update_job(job_id, analysis_status=None)
            await ws.broadcast({"event": "job_failed", "data": {"job_id": job_id, "error": str(e)}})

    asyncio.create_task(run_analysis())
    return {"status": "analyzing", "job_id": job_id}


@router.get("/jobs/{job_id}/scenes")
async def get_scenes(request: Request, job_id: str):
    jm = request.app.state.job_manager
    job = await jm.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    db = request.app.state.db
    scenes = await db.list_scenes(job_id)
    return scenes


@router.put("/jobs/{job_id}/scenes")
async def update_scenes(request: Request, job_id: str):
    jm = request.app.state.job_manager
    job = await jm.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    db = request.app.state.db
    new_scenes = await request.json()

    await db.delete_scenes_for_job(job_id)
    for scene in new_scenes:
        start = scene["start_time"]
        end = scene["end_time"]
        await db.create_scene(
            scene_id=str(uuid.uuid4()),
            job_id=job_id,
            scene_index=scene["scene_index"],
            start_time=start,
            end_time=end,
            duration=round(end - start, 3),
        )

    await db.update_job(job_id, scene_count=len(new_scenes))
    return await db.list_scenes(job_id)


@router.post("/jobs/{job_id}/split", status_code=202)
async def split_scenes(request: Request, job_id: str):
    jm = request.app.state.job_manager
    db = request.app.state.db
    ws = request.app.state.ws_manager
    splitter = request.app.state.splitter

    job = await jm.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    scenes = await db.list_scenes(job_id)
    if not scenes:
        raise HTTPException(status_code=400, detail="No scenes to split")

    await db.update_job(job_id, analysis_status="splitting")

    async def run_split():
        try:
            output_dir = os.path.join(os.path.dirname(job.output_path), "scenes", job_id)

            async def on_progress(pct: int, current_scene: int):
                await ws.broadcast({
                    "event": "split_progress",
                    "data": {"job_id": job_id, "progress": pct, "current_scene": current_scene},
                })

            paths = await splitter.split_all(
                input_path=job.output_path,
                scenes=scenes,
                output_dir=output_dir,
                on_progress=on_progress,
            )

            # Update scene records with split paths
            for scene, path in zip(scenes, paths):
                await db.update_scene(scene["id"], split_path=path)

            await db.update_job(job_id, analysis_status="split_complete")
            await ws.broadcast({
                "event": "split_complete",
                "data": {"job_id": job_id, "scene_count": len(paths)},
            })

        except Exception as e:
            await db.update_job(job_id, analysis_status="analyzed")
            await ws.broadcast({"event": "job_failed", "data": {"job_id": job_id, "error": str(e)}})

    asyncio.create_task(run_split())
    return {"status": "splitting", "job_id": job_id, "scene_count": len(scenes)}


@router.get("/thumbs/{job_id}/{filename}")
async def get_thumbnail(job_id: str, filename: str, request: Request):
    # Construct path based on output base
    jm = request.app.state.job_manager
    job = await jm.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    thumb_path = os.path.join(os.path.dirname(job.output_path), "thumbs", job_id, filename)
    if not os.path.exists(thumb_path):
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(thumb_path, media_type="image/jpeg")
```

**Step 4: Update `backend/digitizer/main.py`**

Add scene_detector and splitter initialization in `create_app`:

```python
from digitizer.scene_detector import SceneDetector
from digitizer.splitter import VideoSplitter

# Inside create_app, after existing initialization:
scene_detector = SceneDetector()
splitter = VideoSplitter()

app.state.scene_detector = scene_detector
app.state.splitter = splitter
```

**Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_scenes_api.py -v`
Expected: All 7 tests PASS

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add backend/digitizer/api.py backend/digitizer/main.py backend/tests/test_scenes_api.py
git commit -m "feat: add scene analysis and split API routes with WebSocket progress"
```

---

## Task 5: Frontend - Scene Review Page

**Files:**
- Create: `frontend/src/app/jobs/[id]/scenes/page.tsx`
- Create: `frontend/src/components/scene-timeline.tsx`
- Create: `frontend/src/components/scene-card.tsx`
- Modify: `frontend/src/app/jobs/[id]/page.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/context/digitizer-context.tsx`

> **REQUIRED:** Use the `frontend-design` skill to build this task.

**What to build:**

1. **Update `types.ts`** - Add Scene type, AnalysisStatus type, scene API response types

2. **Update `api.ts`** - Add functions:
   - `analyzeScenes(jobId)` → POST /api/jobs/{id}/analyze
   - `getScenes(jobId)` → GET /api/jobs/{id}/scenes
   - `updateScenes(jobId, scenes)` → PUT /api/jobs/{id}/scenes
   - `splitScenes(jobId)` → POST /api/jobs/{id}/split
   - `getThumbnailUrl(jobId, filename)` → returns URL string

3. **Update `digitizer-context.tsx`** - Add:
   - `analysisProgress: { jobId: string, progress: number } | null`
   - `splitProgress: { jobId: string, progress: number, currentScene: number } | null`
   - Handle WebSocket events: `analysis_progress`, `analysis_complete`, `split_progress`, `split_complete`

4. **Create `scene-timeline.tsx`** - Timeline visualization:
   - Horizontal bar = full video duration
   - Colored alternating segments for each scene
   - Vertical cut markers at scene boundaries
   - Hover tooltips: "Scene N - start to end (duration)"
   - Click a marker to select it (highlights in the scene list)
   - Responsive width

5. **Create `scene-card.tsx`** - Individual scene card:
   - Thumbnail image (from /thumbs/ endpoint)
   - Scene number, start/end times, duration
   - "Delete" button - removes cut point, merges with next scene
   - "Adjust" button - opens inline time inputs to edit start/end
   - Highlight state when selected from timeline

6. **Create `/jobs/[id]/scenes/page.tsx`** - Scene review page:
   - **Top:** SceneTimeline component
   - **Middle:** Grid of SceneCard components
   - **"Add Cut" button:** Opens modal/inline input for timestamp
   - **Bottom action bar:**
     - "Re-analyze" button with sensitivity slider (threshold 15-35)
     - "Split All" button (disabled during split, shows progress bar)
     - After split: success message with file count
   - Loading states for analysis and split operations

7. **Update Job Detail page** (`/jobs/[id]/page.tsx`):
   - For VHS jobs with status "complete": show "Analyze Scenes" button
   - During analysis: show progress bar with "Detecting scenes..."
   - When analyzed: show "N scenes detected" badge + "Review Scenes" link
   - When split_complete: show "N scenes split" + "Review Scenes" link

**Design notes:**
- Same dark theme control-panel aesthetic
- Timeline should feel like a video editor scrubber
- Scene cards in a responsive grid (3 columns desktop, 2 tablet, 1 mobile)
- Purple accent color for scene-related UI (consistent with VHS badge color)

**After building:** Run `npm run build` to verify compilation. Fix any errors.

**Commit:**
```bash
git add frontend/
git commit -m "feat: add scene review page with timeline, scene cards, and split controls"
```

---

## Task 6: Backend/DevOps - Update Dockerfile for OpenCV

**Files:**
- Modify: `backend/Dockerfile`

**Step 1: Update `backend/Dockerfile`**

Add OpenCV system dependencies:

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg lsdvd dvdbackup eject \
    libgl1-mesa-glx libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY digitizer/ digitizer/

RUN mkdir -p /data /output/dvd /output/vhs

CMD ["uvicorn", "digitizer.main:app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
```

**Step 2: Commit**

```bash
git add backend/Dockerfile
git commit -m "feat: add OpenCV dependencies to backend Dockerfile for scene detection"
```

---

## Parallel Work Assignment (for teams)

| Agent | Tasks | Skills |
|-------|-------|--------|
| **backend** | Tasks 1-4 (sequential: DB → detector → splitter → API) | TDD, Python |
| **frontend** | Task 5 (scene review page) | `frontend-design` skill |
| **devops** | Task 6 (after backend task 2 lands — needs requirements.txt) | Docker |

**Dependencies:**
- Tasks 1-4 are sequential
- Task 5 is independent — can run in parallel with backend
- Task 6 depends on Task 2 (requirements.txt update)
