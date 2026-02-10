# CLAUDE.md - Digitizer Project Guide

## Project Overview

Digitizer is a physical media to MP4 conversion platform. It converts home DVDs and VHS tapes to MP4 files, with AI-powered scene detection for VHS recordings. It runs as a containerized web app on k3s.

## Repository Structure

```
backend/                    # Python/FastAPI backend
  digitizer/
    main.py                 # App factory, create_app(), monitor loop
    api.py                  # All REST + WebSocket routes
    db.py                   # SQLite via aiosqlite (jobs, scenes, settings)
    models.py               # Pydantic models and enums
    config.py               # Pydantic settings with DIGITIZER_ env prefix
    jobs.py                 # Job lifecycle manager
    ripper.py               # DVD FFmpeg remux
    capture.py              # VHS HDMI capture (V4L2 -> H.264)
    drive_monitor.py        # DVD drive polling with lsdvd
    scene_detector.py       # PySceneDetect wrapper (ContentDetector + ThresholdDetector)
    splitter.py             # FFmpeg video segment splitter
    ws.py                   # WebSocket connection manager
  tests/                    # pytest tests (72 total)
  requirements.txt
  Dockerfile

frontend/                   # Next.js 14 App Router frontend
  src/
    app/                    # Pages: /, /jobs, /jobs/[id], /jobs/[id]/scenes, /settings
    components/             # UI components (sidebar, drive-status-card, vhs-capture-card, etc.)
    context/                # digitizer-context.tsx - WebSocket state management
    lib/                    # api.ts, types.ts, utils.ts
  Dockerfile

k8s/                        # k3s deployment manifests
  namespace.yaml
  storage.yaml              # PVC for SQLite + NFS PV/PVC (has CHANGE THIS placeholders)
  backend-deployment.yaml   # Privileged pod, /dev/sr0 + /dev/video0
  frontend-deployment.yaml
  services.yaml
  ingress.yaml              # nginx ingress (has CHANGE THIS placeholder for hostname)

docker-compose.dev.yml      # Local dev with device passthrough
docs/plans/                 # Design specs and implementation plans
```

## Tech Stack

- **Backend:** Python 3.12, FastAPI, uvicorn, aiosqlite, FFmpeg, lsdvd, PySceneDetect, OpenCV
- **Frontend:** Next.js 14, TypeScript, Tailwind CSS
- **Database:** SQLite (async via aiosqlite)
- **Deployment:** Docker, k3s, NFS

## Key Patterns

### Backend

- **App factory pattern:** `create_app()` in `main.py` builds the FastAPI app. Tests use it with `start_monitor=False` to skip the drive polling loop.
- **State on app:** All shared objects (db, ws_manager, job_manager, ripper, capture, scene_detector, splitter) are stored on `app.state`.
- **Async everything:** All DB calls, FFmpeg processes, and WebSocket broadcasts are async.
- **FFmpeg subprocess:** ripper.py, capture.py, splitter.py, and scene_detector.py all spawn FFmpeg via `asyncio.create_subprocess_exec`. Progress is parsed from stderr.
- **WebSocket broadcast:** `ws.py` ConnectionManager broadcasts events to all connected clients. Dead connections are cleaned up automatically.
- **Background tasks:** Long-running operations (rip, capture, analyze, split) run as `asyncio.create_task()` fire-and-forget tasks, broadcasting progress via WebSocket.

### Frontend

- **WebSocket context:** `digitizer-context.tsx` provides all real-time state (drive status, capture status, job progress, analysis progress) via React context.
- **Auto-reconnect:** WebSocket reconnects with exponential backoff (1s -> 30s max).
- **API client:** `lib/api.ts` has typed functions for all endpoints. Base URL from `NEXT_PUBLIC_API_URL`.
- **Dark theme:** CSS variables in globals.css, control-panel aesthetic throughout.

### Testing

- **Backend:** pytest + pytest-asyncio. 72 tests. All async. Uses `tmp_db_path` and `tmp_output_dir` fixtures from `conftest.py`.
- **Test the API via httpx:** `AsyncClient` with `ASGITransport` for integration tests against the actual FastAPI app.
- **Mock FFmpeg/lsdvd:** External commands are mocked in tests. Never call real FFmpeg in tests.

## Common Commands

```bash
# Run backend tests
cd backend && python -m pytest tests/ -v

# Run a specific test file
cd backend && python -m pytest tests/test_api.py -v

# Build frontend
cd frontend && npm run build

# Dev frontend
cd frontend && npm run dev

# Docker compose (needs /dev/sr0 and /dev/video0)
docker compose -f docker-compose.dev.yml up --build
```

## Database Schema

Three tables in SQLite:

- **jobs** - id, source_type (dvd/vhs), disc_info (JSON), status, progress, output_path, file_size, started_at, completed_at, error, analysis_status, scene_count
- **scenes** - id, job_id, scene_index, start_time, end_time, duration, thumbnail_path, split_path
- **settings** - key/value pairs (output_path, auto_eject, encoding_preset, crf_quality, etc.)

## Environment Variables

All backend config uses `DIGITIZER_` prefix. See README.md for the full list.

Frontend uses `NEXT_PUBLIC_API_URL` (default http://localhost:8000).

## Important Notes

- k8s manifests have `# <-- CHANGE THIS` placeholders for NFS server IP, export path, and ingress hostname
- Backend pod runs privileged for device access (/dev/sr0, /dev/video0)
- No authentication - single-user home tool
- No commercial DVD decryption (no libdvdcss)
- DVD ripping is direct remux (no transcoding). VHS capture encodes to H.264.
