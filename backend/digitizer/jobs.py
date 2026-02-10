import uuid
from datetime import datetime, timezone

from digitizer.db import Database
from digitizer.models import Job, JobStatus, DiscInfo


class JobManager:
    def __init__(self, db: Database, output_base: str = "/output/dvd", vhs_output_base: str = "/output/vhs"):
        self.db = db
        self.output_base = output_base
        self.vhs_output_base = vhs_output_base

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

    async def get_job(self, job_id: str) -> Job | None:
        row = await self.db.get_job(job_id)
        if row is None:
            return None
        return self._row_to_job(row)

    async def list_jobs(self, limit: int = 10, offset: int = 0, source_type: str | None = None) -> list[Job]:
        rows = await self.db.list_jobs(limit=limit, offset=offset, source_type=source_type)
        return [self._row_to_job(r) for r in rows]

    async def mark_ripping(self, job_id: str) -> Job:
        await self.db.update_job(job_id, status="ripping")
        return await self.get_job(job_id)

    async def update_progress(self, job_id: str, progress: int) -> Job:
        await self.db.update_job(job_id, progress=min(progress, 100))
        return await self.get_job(job_id)

    async def mark_complete(self, job_id: str, file_size: int) -> Job:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.update_job(
            job_id,
            status="complete",
            progress=100,
            file_size=file_size,
            completed_at=now,
        )
        return await self.get_job(job_id)

    async def mark_failed(self, job_id: str, error: str) -> Job:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.update_job(
            job_id, status="failed", error=error, completed_at=now
        )
        return await self.get_job(job_id)

    async def delete_job(self, job_id: str) -> bool:
        return await self.db.delete_job(job_id)

    def _row_to_job(self, row: dict) -> Job:
        disc_info = row.get("disc_info", {})
        if isinstance(disc_info, str):
            import json
            disc_info = json.loads(disc_info)
        return Job(
            id=row["id"],
            source_type=row["source_type"],
            disc_info=DiscInfo(**disc_info) if disc_info else DiscInfo(),
            status=row["status"],
            progress=row["progress"],
            output_path=row.get("output_path"),
            file_size=row.get("file_size"),
            started_at=row.get("started_at"),
            completed_at=row.get("completed_at"),
            error=row.get("error"),
            analysis_status=row.get("analysis_status"),
            scene_count=row.get("scene_count"),
        )
