import asyncio
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from digitizer.api import router
from digitizer.capture import VHSCapture
from digitizer.db import Database
from digitizer.drive_monitor import DriveMonitor
from digitizer.jobs import JobManager
from digitizer.ripper import DVDRipper
from digitizer.scene_detector import SceneDetector
from digitizer.splitter import VideoSplitter
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
    _capture_device = os.environ.get("DIGITIZER_CAPTURE_DEVICE", "/dev/video0")
    _vhs_output = os.environ.get("DIGITIZER_VHS_OUTPUT_PATH", "/output/vhs")

    db = Database(_db_path)
    await db.init()

    ws_manager = ConnectionManager()
    drive_monitor = DriveMonitor(device=_device)
    ripper = DVDRipper(drive_device=_device)
    job_manager = JobManager(db=db, output_base=_output_base, vhs_output_base=_vhs_output)
    vhs_capture = VHSCapture(
        capture_device=_capture_device,
        encoding_preset=os.environ.get("DIGITIZER_ENCODING_PRESET", "fast"),
        crf_quality=int(os.environ.get("DIGITIZER_CRF_QUALITY", "23")),
        audio_bitrate=os.environ.get("DIGITIZER_AUDIO_BITRATE", "192k"),
    )

    scene_detector = SceneDetector()
    splitter = VideoSplitter()

    app.state.db = db
    app.state.ws_manager = ws_manager
    app.state.drive_monitor = drive_monitor
    app.state.ripper = ripper
    app.state.job_manager = job_manager
    app.state.vhs_capture = vhs_capture
    app.state.scene_detector = scene_detector
    app.state.splitter = splitter
    app.state._capture_job_id = None

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


def app_factory():
    """Synchronous factory that returns an ASGI app with lifespan-managed init."""
    from contextlib import asynccontextmanager

    _app_ref: dict = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: initialize all components
        _db_path = os.environ.get("DIGITIZER_DB_PATH", "/data/digitizer.db")
        _output_base = os.environ.get("DIGITIZER_OUTPUT_BASE_PATH", "/output/dvd")
        _device = os.environ.get("DIGITIZER_DRIVE_DEVICE", "/dev/sr0")
        _capture_device = os.environ.get("DIGITIZER_CAPTURE_DEVICE", "/dev/video0")
        _vhs_output = os.environ.get("DIGITIZER_VHS_OUTPUT_PATH", "/output/vhs")

        db = Database(_db_path)
        await db.init()

        ws_manager = ConnectionManager()
        drive_monitor = DriveMonitor(device=_device)
        ripper = DVDRipper(drive_device=_device)
        job_manager = JobManager(db=db, output_base=_output_base, vhs_output_base=_vhs_output)
        vhs_capture = VHSCapture(
            capture_device=_capture_device,
            encoding_preset=os.environ.get("DIGITIZER_ENCODING_PRESET", "fast"),
            crf_quality=int(os.environ.get("DIGITIZER_CRF_QUALITY", "23")),
            audio_bitrate=os.environ.get("DIGITIZER_AUDIO_BITRATE", "192k"),
        )
        scene_detector = SceneDetector()
        splitter = VideoSplitter()

        app.state.db = db
        app.state.ws_manager = ws_manager
        app.state.drive_monitor = drive_monitor
        app.state.ripper = ripper
        app.state.job_manager = job_manager
        app.state.vhs_capture = vhs_capture
        app.state.scene_detector = scene_detector
        app.state.splitter = splitter
        app.state._capture_job_id = None

        monitor_task = asyncio.create_task(_monitor_loop(app))

        yield

        # Shutdown
        monitor_task.cancel()
        await db.close()

    app = FastAPI(title="Digitizer", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("digitizer.main:app_factory", host="0.0.0.0", port=8000, factory=True)
