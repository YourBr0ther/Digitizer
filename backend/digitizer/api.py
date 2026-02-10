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
async def list_jobs(request: Request, limit: int = 10, offset: int = 0, source_type: str | None = None):
    jm = request.app.state.job_manager
    jobs = await jm.list_jobs(limit=limit, offset=offset, source_type=source_type)
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


@router.get("/capture/status")
async def capture_status(request: Request):
    vhs = request.app.state.vhs_capture
    return {
        "status": "recording" if vhs.is_recording else "idle",
        "job_id": getattr(request.app.state, "_capture_job_id", None),
    }


@router.post("/capture/start")
async def capture_start(request: Request):
    import asyncio as _asyncio
    import os as _os

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
                if _os.path.exists(job.output_path):
                    final_size = _os.path.getsize(job.output_path)
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

    _asyncio.create_task(run_capture())

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


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    manager = websocket.app.state.ws_manager
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
