# Digitizer Phase 3 - AI Scene Detection Design

**Date:** 2026-02-09
**Status:** Approved
**Depends on:** Phase 2 (complete)

## Purpose

Add automatic scene detection and video splitting to VHS captures. Detects hard cuts, fade-to-black, and static/noise between recordings. Auto-splits into separate MP4 files and provides a UI for reviewing/adjusting cut points before re-splitting.

## Detection Pipeline

```
Completed VHS MP4 → PySceneDetect (3 detectors) → Scene list + thumbnails → FFmpeg split → Individual MP4s
```

### Detectors

1. **ContentDetector** - Hard cuts via frame-to-frame content change. Threshold: 22.0 (lower than default for VHS noise)
2. **ThresholdDetector** - Fade-to-black via brightness threshold: 12
3. **Static/noise filter** - Post-processing pass: scenes < 2s with high variance are merged with adjacent scenes

### Output Structure

```
/output/vhs/scenes/{job_id}/
  scene_001.mp4
  scene_002.mp4
  ...
/output/vhs/thumbs/{job_id}/
  scene_001.jpg
  scene_002.jpg
  ...
```

## New Backend Modules

### scene_detector.py

- `analyze(video_path, on_progress) -> list[Scene]`
- Uses PySceneDetect ContentDetector + ThresholdDetector
- Post-filters static/noise (short scenes with high variance)
- Extracts thumbnail at each cut point via FFmpeg
- Returns scene list with timestamps and thumbnail paths

### splitter.py

- `split(video_path, scenes, output_dir, on_progress) -> list[str]`
- FFmpeg segment copy per scene: `ffmpeg -ss {start} -to {end} -c copy`
- No re-encoding, fast
- Returns list of output file paths

## Database Changes

New table:

```sql
CREATE TABLE scenes (
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

Job table additions (new columns):
- `analysis_status` TEXT nullable: null | "analyzing" | "analyzed" | "splitting" | "split_complete"
- `scene_count` INTEGER nullable

## New API Routes

- `POST /api/jobs/{id}/analyze` - Start scene detection. Returns 202.
- `GET /api/jobs/{id}/scenes` - Get detected scenes.
- `PUT /api/jobs/{id}/scenes` - Update scene cut points (user edits).
- `POST /api/jobs/{id}/split` - Run split with current scenes. Returns 202.
- `GET /thumbs/{job_id}/{filename}` - Serve thumbnail images.

## New WebSocket Events

- `analysis_progress` - { job_id, progress: 0-100 }
- `analysis_complete` - { job_id, scene_count }
- `split_progress` - { job_id, progress: 0-100, current_scene }
- `split_complete` - { job_id, scene_count }

## Frontend Changes

### New Page: /jobs/[id]/scenes

**Timeline bar:** Horizontal bar showing full duration, cut markers, colored scene segments, hover tooltips.

**Scene list:** Card grid with thumbnails, timestamps, duration. Each card has Delete (merge) and Adjust (time edit) buttons. "Add Cut" button for manual cuts.

**Action bar:** Re-analyze button with sensitivity slider (threshold 15-35), Split All button, progress bar during operations.

### Job Detail Page Updates

- VHS jobs show "Analyze Scenes" button when analysis_status is null
- Shows spinner during analysis
- Shows scene count + "Review Scenes" link when analyzed
- Shows split file count when split_complete

## New Dependencies

- `scenedetect[opencv]` - PySceneDetect with OpenCV backend
- Backend Dockerfile: add `libgl1-mesa-glx libglib2.0-0` for OpenCV

## Out of Scope

- Live preview/playback in browser
- GPU-accelerated detection
- ML-based detection (future enhancement)
- Audio-based scene detection
