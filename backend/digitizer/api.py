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
async def websocket_endpoint(websocket: WebSocket):
    manager = websocket.app.state.ws_manager
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
