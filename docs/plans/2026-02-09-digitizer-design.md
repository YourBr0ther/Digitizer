# Digitizer - Design Specification

**Date:** 2026-02-09
**Status:** Approved
**Project:** Digitizer - Physical Media to MP4 Conversion Platform

## Purpose

Digitizer is a self-hosted, containerized platform for converting home DVDs and VHS tapes to MP4 files. It runs on a single k3s node with attached USB hardware (DVD drive, HDMI capture card) and provides a web UI for monitoring and managing rip/capture jobs.

## Phasing

- **Phase 1 (current):** DVD ripping - auto-detect disc insertion, remux to MP4, save to NFS
- **Phase 2 (future):** HDMI/VHS capture via USB capture card
- **Phase 3 (future):** AI-powered scene detection to split VHS recordings at cuts

---

## Phase 1 Scope - DVD Ripping

### User Workflow

1. User inserts a home-burned DVD into the USB DVD drive
2. System auto-detects the disc within ~2 seconds
3. System reads DVD structure, identifies the main title
4. FFmpeg remuxes the main title VOBs directly into an MP4 container (no transcoding)
5. Output saved to NFS share at `/output/dvd/YYYY-MM-DD_rip_NNN.mp4`
6. Disc is ejected on completion
7. Web UI shows real-time progress throughout

### Architecture

Two-container system deployed in the `digitizer` k3s namespace:

```
[USB DVD Drive /dev/sr0]
        |
[digitizer-backend]  ----WebSocket/REST---->  [digitizer-frontend]
   Python + FastAPI                              Next.js App Router
   FFmpeg, lsdvd                                 Tailwind CSS
   SQLite (/data)                                Port 3000
   Port 8000
        |
[NFS Share /output]
```

### Backend - digitizer-backend

**Runtime:** Python 3.12, FastAPI, uvicorn
**System deps:** FFmpeg, lsdvd, dvdbackup

#### Modules

**`drive_monitor.py`**
- Background asyncio task polling `/dev/sr0` every 2 seconds
- Detects disc insertion by checking device readiness
- On detection: reads disc structure via `lsdvd`, creates a job record, enqueues rip
- On eject: updates drive status
- Publishes drive state changes to WebSocket subscribers

**`ripper.py`**
- Receives a job with disc info (main title, duration)
- Runs FFmpeg to remux VOB files from the DVD into MP4 container
- Streams progress (percent based on time/duration) via callback
- On completion: records final file size, marks job complete, triggers disc eject

**`jobs.py`**
- Job lifecycle: `detected` -> `ripping` -> `complete` | `failed`
- Job record fields:
  - `id` (UUID)
  - `source_type` ("dvd")
  - `disc_info` (JSON - title count, main title, duration)
  - `status` (enum)
  - `progress` (0-100)
  - `output_path` (string)
  - `file_size` (bytes, null until complete)
  - `started_at` (timestamp)
  - `completed_at` (timestamp, nullable)
  - `error` (string, nullable)

**`api.py`**
- `GET /api/health` - health check
- `GET /api/drive` - current drive status (empty / disc_detected / ripping)
- `GET /api/jobs` - paginated job history
- `GET /api/jobs/{id}` - single job detail
- `DELETE /api/jobs/{id}` - delete job record (not the file)
- `GET /api/settings` - current settings
- `PUT /api/settings` - update settings
- `WS /api/ws` - WebSocket for real-time events:
  - `drive_status` - drive state changes
  - `job_progress` - rip progress updates (every 1-2s)
  - `job_complete` - rip finished
  - `job_failed` - rip error

**`db.py`**
- SQLite via aiosqlite
- Tables: `jobs`, `settings`
- DB file stored at `/data/digitizer.db` (persistent volume)

**`config.py`**
- Output base path (default: `/output/dvd`)
- Naming pattern (default: `YYYY-MM-DD_rip_NNN`)
- Auto-eject on complete (default: true)
- Drive device path (default: `/dev/sr0`)
- Poll interval (default: 2s)

#### Python Dependencies

```
fastapi
uvicorn[standard]
aiosqlite
pydantic
python-dotenv
```

### Frontend - digitizer-frontend

**Runtime:** Node.js 20, Next.js (App Router)
**Styling:** Tailwind CSS

#### Pages

**`/` - Dashboard**
- Drive status card: large indicator showing "No Disc" / "Disc Detected" / "Ripping..."
- Active job: progress bar with percentage, elapsed time, estimated file size
- Recent jobs: last 10 completed/failed rips as cards with status badges

**`/jobs` - History**
- Full paginated table of all jobs
- Columns: date, filename, source type, duration, file size, status
- Click row to navigate to detail

**`/jobs/[id]` - Job Detail**
- Full metadata display
- Output file path
- Error log if failed
- Duration, file size

**`/settings` - Settings**
- Output path configuration
- Naming format
- Auto-eject toggle
- Source type default (preps for phase 2)

#### Real-time Updates

- `useDigitizerSocket` hook: connects to `WS /api/ws` on app mount
- Pushes drive status and job progress into React context
- All dashboard components subscribe to this context
- Auto-reconnect on disconnect

#### Design Direction

- Dark theme, utility/control-panel aesthetic
- Status-at-a-glance priority
- Minimal interaction needed (matches the auto-rip workflow)
- Responsive but desktop-primary

### Deployment - k3s

#### Namespace

`digitizer`

#### Backend Deployment

```yaml
spec:
  replicas: 1
  containers:
    - name: digitizer-backend
      image: digitizer-backend:latest
      ports: [8000]
      securityContext:
        privileged: true  # for /dev/sr0 access
      volumeMounts:
        - name: output
          mountPath: /output
        - name: data
          mountPath: /data
      env:
        - name: OUTPUT_PATH
          value: /output/dvd
        - name: DRIVE_DEVICE
          value: /dev/sr0
  volumes:
    - name: output
      nfs:
        server: <nfs-server-ip>
        path: <nfs-export-path>
    - name: data
      persistentVolumeClaim:
        claimName: digitizer-db
  nodeSelector:
    digitizer/dvd-drive: "true"
```

#### Frontend Deployment

```yaml
spec:
  replicas: 1
  containers:
    - name: digitizer-frontend
      image: digitizer-frontend:latest
      ports: [3000]
      env:
        - name: BACKEND_URL
          value: http://digitizer-backend:8000
```

#### Services

- `digitizer-backend`: ClusterIP, port 8000
- `digitizer-frontend`: ClusterIP, port 3000

#### Ingress

Single ingress with:
- `/api/*` and `/api/ws` -> digitizer-backend:8000
- `/*` -> digitizer-frontend:3000

#### Storage

- **SQLite PVC:** 1Gi, `local-path` provisioner, mounted at `/data`
- **NFS PV/PVC:** Points to user's NFS server, mounted at `/output`

#### Device Passthrough

USB DVD drive presents as `/dev/sr0`. Backend pod runs privileged or with explicit device access. Node labeled `digitizer/dvd-drive=true` for scheduling affinity.

### Docker Images

**digitizer-backend Dockerfile:**
```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg lsdvd dvdbackup eject \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "digitizer.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**digitizer-frontend Dockerfile:**
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
ENV PORT=3000
CMD ["node", "server.js"]
```

---

## Out of Scope

- Commercial DVD decryption (no libdvdcss)
- Transcoding / re-encoding (remux only)
- Multi-drive support
- User authentication
- Cloud storage / S3
- Mobile-optimized UI

## Future Phases (Reference Only)

### Phase 2 - HDMI/VHS Capture
- V4L2 capture from `/dev/video0` (USB HDMI capture card)
- Manual start/stop recording from UI
- FFmpeg encoding from video device to MP4
- Output: `/output/vhs/YYYY-MM-DD_capture_NNN.mp4`

### Phase 3 - AI Scene Detection
- Post-processing pipeline for VHS captures
- PySceneDetect or ML model for cut detection (hard cuts, fades, static)
- Auto-split into separate MP4 files per scene
- UI for reviewing/adjusting detected cut points
