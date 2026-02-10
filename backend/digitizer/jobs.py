import uuid
from datetime import datetime, timezone

from digitizer.db import Database
from digitizer.models import Job, JobStatus, DiscInfo


class JobManager:
    def __init__(self, db: Database, output_base: str = "/output/dvd"):
        self.db = db
        self.output_base = output_base

    async def create_job(self, disc_info: dict) -> Job:
        job_id = str(uuid.uuid4())
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        seq = await self.db.get_next_sequence(today)
        output_path = f"{self.output_base}/{today}_rip_{seq:03d}.mp4"

        await self.db.create_job(
            job_id=job_id,
            source_type="dvd",
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

    async def list_jobs(self, limit: int = 10, offset: int = 0) -> list[Job]:
        rows = await self.db.list_jobs(limit=limit, offset=offset)
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
        )
