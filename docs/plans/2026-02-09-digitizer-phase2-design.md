# Digitizer Phase 2 - HDMI/VHS Capture Design

**Date:** 2026-02-09
**Status:** Approved
**Depends on:** Phase 1 (complete)

## Purpose

Add real-time HDMI capture for VHS tapes to the Digitizer platform. Uses a generic USB HDMI capture dongle with a composite-to-HDMI adapter chain from the VCR.

## Hardware Chain

```
VCR (composite out) → Composite-to-HDMI adapter → USB HDMI capture dongle → /dev/video0
```

## Capture Pipeline

```
/dev/video0 (V4L2) → FFmpeg → H.264/AAC MP4 → /output/vhs/YYYY-MM-DD_capture_NNN.mp4
```

FFmpeg command:
```
ffmpeg -f v4l2 -i /dev/video0 \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  /output/vhs/2026-02-09_capture_001.mp4
```

## User Workflow

1. Connect VCR to composite-to-HDMI adapter, adapter to USB capture dongle
2. Open Digitizer web UI, navigate to Dashboard
3. Press Play on VCR
4. Click "Start Capture" button in the VHS Capture card
5. Watch elapsed time and file size grow in real-time
6. When tape is done, click "Stop Capture"
7. FFmpeg gracefully stops (SIGINT), writes final MP4
8. Job appears in history with source_type "vhs"

## New Backend Module: capture.py

**Capture state:** `idle` | `recording` (independent of DVD drive status)

**Lifecycle:**
- Start: Create job (source_type=vhs, status=ripping), spawn FFmpeg process
- During: Monitor stderr for elapsed time, broadcast progress via WebSocket
- Stop: Send SIGINT to FFmpeg, wait for clean exit, mark job complete
- Error: FFmpeg crash → mark job failed

**Edge cases:**
- Start while already recording → 409 Conflict
- Stop while not recording → 404 Not Found
- FFmpeg crashes → job marked failed with error message
- HDMI signal lost → FFmpeg errors out, job marked failed

## New API Routes

- `POST /api/capture/start` - Start recording. Returns new job. 409 if already recording.
- `POST /api/capture/stop` - Stop recording. Returns completed job. 404 if not recording.
- `GET /api/capture/status` - Returns { status: "idle"|"recording", job_id: str|null }

## New WebSocket Events

- `capture_status` - { status: "idle"|"recording" }
- Reuses: `job_progress`, `job_complete`, `job_failed` (distinguished by source_type)

## Frontend Changes

**Dashboard:** Two-panel layout
- Left: DVD Drive Status (existing)
- Right: VHS Capture card (new)
  - Idle: "Ready to Capture" + green "Start Capture" button
  - Recording: Elapsed time, file size, red pulsing dot, red "Stop Capture" button

**Job History:** Source type filter dropdown (All / DVD / VHS)

**Settings:** New VHS section
- VHS output path (default: /output/vhs)
- Encoding preset: fast (default) / medium / slow
- CRF quality: slider 18-28, default 23

## New Config Fields

```python
capture_device: str = "/dev/video0"
vhs_output_path: str = "/output/vhs"
encoding_preset: str = "fast"
crf_quality: int = 23
audio_bitrate: str = "192k"
```

## Deployment Changes

Backend deployment: add env vars
- `DIGITIZER_CAPTURE_DEVICE=/dev/video0`
- `DIGITIZER_VHS_OUTPUT_PATH=/output/vhs`

No new containers, services, or ingress changes.

## Database

No schema changes. Reuses jobs table with source_type="vhs".

## Out of Scope

- HDMI signal auto-detection
- Audio level monitoring
- Live preview in browser
- Multiple simultaneous captures
