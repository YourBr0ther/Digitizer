import json

import aiosqlite


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def init(self):
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL DEFAULT 'dvd',
                disc_info TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'detected',
                progress INTEGER NOT NULL DEFAULT 0,
                output_path TEXT,
                file_size INTEGER,
                started_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT,
                error TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT OR IGNORE INTO settings (key, value) VALUES ('output_path', '/output/dvd');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('naming_pattern', 'YYYY-MM-DD_rip_NNN');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_eject', 'true');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('vhs_output_path', '/output/vhs');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('encoding_preset', 'fast');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('crf_quality', '23');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('audio_bitrate', '192k');
            """
        )
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def create_job(
        self, job_id: str, source_type: str, disc_info: dict, output_path: str | None = None
    ):
        await self._conn.execute(
            "INSERT INTO jobs (id, source_type, disc_info, output_path) VALUES (?, ?, ?, ?)",
            (job_id, source_type, json.dumps(disc_info), output_path),
        )
        await self._conn.commit()

    async def get_job(self, job_id: str) -> dict | None:
        cursor = await self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        job = dict(row)
        job["disc_info"] = json.loads(job["disc_info"])
        return job

    async def list_jobs(self, limit: int = 10, offset: int = 0, source_type: str | None = None) -> list[dict]:
        if source_type:
            cursor = await self._conn.execute(
                "SELECT * FROM jobs WHERE source_type = ? ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (source_type, limit, offset),
            )
        else:
            cursor = await self._conn.execute(
                "SELECT * FROM jobs ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        rows = await cursor.fetchall()
        jobs = []
        for row in rows:
            job = dict(row)
            job["disc_info"] = json.loads(job["disc_info"])
            jobs.append(job)
        return jobs

    async def update_job(self, job_id: str, **kwargs):
        allowed = {"status", "progress", "output_path", "file_size", "completed_at", "error"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [job_id]
        await self._conn.execute(
            f"UPDATE jobs SET {set_clause} WHERE id = ?", values
        )
        await self._conn.commit()

    async def delete_job(self, job_id: str) -> bool:
        cursor = await self._conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        await self._conn.commit()
        return cursor.rowcount > 0

    async def get_settings(self) -> dict:
        cursor = await self._conn.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        result = {}
        for row in rows:
            val = row["value"]
            if val in ("true", "false"):
                val = val == "true"
            result[row["key"]] = val
        return result

    async def update_settings(self, **kwargs):
        for key, value in kwargs.items():
            if isinstance(value, bool):
                value = "true" if value else "false"
            await self._conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )
        await self._conn.commit()

    async def get_next_sequence(self, date_str: str) -> int:
        cursor = await self._conn.execute(
            "SELECT COUNT(*) as cnt FROM jobs WHERE output_path LIKE ?",
            (f"%{date_str}%",),
        )
        row = await cursor.fetchone()
        return row["cnt"] + 1
