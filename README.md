# Digitizer

Self-hosted platform for converting physical media (DVDs, VHS tapes) to MP4 files. Runs on a single k3s node with a web UI for monitoring and managing jobs.

## Features

**DVD Ripping**
- Auto-detects disc insertion via USB DVD drive
- FFmpeg direct remux (no transcoding) to MP4
- Auto-eject on completion
- Real-time progress via WebSocket

**VHS HDMI Capture**
- Records from USB HDMI capture dongle (V4L2)
- Manual start/stop from the web UI
- H.264/AAC encoding with configurable quality (CRF, preset, bitrate)
- VCR → composite-to-HDMI adapter → USB capture card

**AI Scene Detection**
- PySceneDetect analyzes VHS captures for cuts
- Detects hard cuts, fade-to-black, and static/noise between recordings
- Auto-splits video into separate MP4 files per scene
- Web UI for reviewing, adjusting, and re-splitting scenes with timeline visualization

## Architecture

```
[USB DVD /dev/sr0]  [USB HDMI /dev/video0]
        \                /
     [digitizer-backend]  ----WebSocket/REST---->  [digitizer-frontend]
        Python 3.12                                   Next.js 14
        FastAPI + FFmpeg                              Tailwind CSS
        PySceneDetect                                 Dark theme UI
        SQLite (/data)                                Port 3000
        Port 8000
             |
      [NFS Share /output]
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, uvicorn, aiosqlite |
| Video | FFmpeg, lsdvd, dvdbackup, PySceneDetect, OpenCV |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Database | SQLite |
| Deployment | Docker, k3s, NFS storage |

## Quick Start (Docker Compose)

```bash
# Clone
git clone git@github.com:YourBr0ther/Digitizer.git
cd Digitizer

# Start both services
docker compose -f docker-compose.dev.yml up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api/health

> **Note:** Docker Compose requires `/dev/sr0` (DVD drive) and `/dev/video0` (HDMI capture) to be present on the host.

## k3s Deployment

### Prerequisites

1. k3s cluster with nginx ingress controller
2. NFS server for media output storage
3. USB DVD drive and/or USB HDMI capture card attached to the node

### Steps

1. **Label your node** (the one with USB devices attached):
   ```bash
   kubectl label node <node-name> digitizer/dvd-drive=true
   ```

2. **Configure NFS storage** - edit `k8s/storage.yaml`:
   - Set your NFS server IP
   - Set your NFS export path

3. **Configure ingress** - edit `k8s/ingress.yaml`:
   - Set your hostname or IP

4. **Build and load images** (or push to a registry):
   ```bash
   docker build -t digitizer-backend:latest ./backend
   docker build -t digitizer-frontend:latest ./frontend
   ```

5. **Deploy**:
   ```bash
   kubectl apply -f k8s/namespace.yaml
   kubectl apply -f k8s/storage.yaml
   kubectl apply -f k8s/backend-deployment.yaml
   kubectl apply -f k8s/frontend-deployment.yaml
   kubectl apply -f k8s/services.yaml
   kubectl apply -f k8s/ingress.yaml
   ```

## Configuration

All backend settings are configured via environment variables with the `DIGITIZER_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `DIGITIZER_DB_PATH` | `/data/digitizer.db` | SQLite database path |
| `DIGITIZER_OUTPUT_BASE_PATH` | `/output/dvd` | DVD output directory |
| `DIGITIZER_VHS_OUTPUT_PATH` | `/output/vhs` | VHS output directory |
| `DIGITIZER_DRIVE_DEVICE` | `/dev/sr0` | DVD drive device path |
| `DIGITIZER_CAPTURE_DEVICE` | `/dev/video0` | HDMI capture device path |
| `DIGITIZER_POLL_INTERVAL` | `2.0` | Drive poll interval (seconds) |
| `DIGITIZER_ENCODING_PRESET` | `fast` | FFmpeg H.264 preset |
| `DIGITIZER_CRF_QUALITY` | `23` | FFmpeg CRF value (18-28) |
| `DIGITIZER_AUDIO_BITRATE` | `192k` | AAC audio bitrate |

Frontend uses `NEXT_PUBLIC_API_URL` (default: `http://localhost:8000`).

## API Reference

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/drive` | DVD drive status |
| GET | `/api/jobs` | List jobs (supports `?source_type=dvd\|vhs`) |
| GET | `/api/jobs/{id}` | Get job detail |
| DELETE | `/api/jobs/{id}` | Delete job record |
| GET | `/api/settings` | Get settings |
| PUT | `/api/settings` | Update settings |
| GET | `/api/capture/status` | VHS capture status |
| POST | `/api/capture/start` | Start VHS recording |
| POST | `/api/capture/stop` | Stop VHS recording |
| POST | `/api/jobs/{id}/analyze` | Start scene detection |
| GET | `/api/jobs/{id}/scenes` | Get detected scenes |
| PUT | `/api/jobs/{id}/scenes` | Update scene cut points |
| POST | `/api/jobs/{id}/split` | Split video at scene cuts |

### WebSocket

Connect to `WS /api/ws` for real-time events:

- `drive_status` - DVD drive state changes
- `capture_status` - VHS capture state changes
- `job_progress` - Rip/capture progress updates
- `job_complete` / `job_failed` - Job completion
- `analysis_progress` / `analysis_complete` - Scene detection progress
- `split_progress` / `split_complete` - Video splitting progress

## Output Structure

```
/output/
  dvd/
    2026-02-09_rip_001.mp4
    2026-02-09_rip_002.mp4
  vhs/
    2026-02-09_capture_001.mp4
    scenes/{job_id}/
      scene_001.mp4
      scene_002.mp4
    thumbs/{job_id}/
      scene_001.jpg
      scene_002.jpg
```

## Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m pytest tests/ -v
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Testing

```bash
# Backend - 72 tests
cd backend && python -m pytest tests/ -v

# Frontend - build check
cd frontend && npm run build
```

## License

MIT
