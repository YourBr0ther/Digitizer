import asyncio
import logging
import os
import re
import shutil
import tempfile
from collections.abc import Callable, Awaitable
from pathlib import Path

logger = logging.getLogger(__name__)

TIME_PATTERN = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")


class DVDRipper:
    def __init__(self, drive_device: str = "/dev/sr0"):
        self.drive_device = drive_device

    def build_ffmpeg_command(
        self, vob_path: str, output_path: str
    ) -> list[str]:
        return [
            "ffmpeg",
            "-y",
            "-hwaccel", "auto",
            "-i", vob_path,
            "-c", "copy",
            "-movflags", "+faststart",
            output_path,
        ]

    def parse_time_from_progress(self, line: str) -> float | None:
        match = TIME_PATTERN.search(line)
        if not match:
            return None
        h, m, s, cs = match.groups()
        return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100

    def calculate_progress(self, current_seconds: float, total_seconds: float) -> int:
        if total_seconds <= 0:
            return 0
        return min(int((current_seconds / total_seconds) * 100), 100)

    async def rip(
        self,
        title_number: int,
        duration: float,
        output_path: str,
        on_progress: Callable[[int], Awaitable[None]] | None = None,
    ) -> bool:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Create temporary directory for DVD extraction
        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Extract DVD title using dvdbackup
            logger.info("Extracting DVD title %d using dvdbackup", title_number)
            backup_cmd = [
                "dvdbackup",
                "-i", self.drive_device,
                "-o", tmpdir,
                "-t", str(title_number),
            ]

            proc = await asyncio.create_subprocess_exec(
                *backup_cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

            if proc.returncode != 0:
                logger.error("dvdbackup exited with code %d", proc.returncode)
                return False

            # Step 2: Find the VOB files in the extracted directory
            video_ts_dirs = list(Path(tmpdir).rglob("VIDEO_TS"))
            if not video_ts_dirs:
                logger.error("No VIDEO_TS directory found after extraction")
                return False

            video_ts = video_ts_dirs[0]
            vob_files = sorted(video_ts.glob("VTS_*_[1-9].VOB"))

            if not vob_files:
                logger.error("No VOB files found in VIDEO_TS")
                return False

            # Step 3: Convert VOB to MP4 using FFmpeg
            # Use concat protocol if multiple VOB files, otherwise single file
            if len(vob_files) == 1:
                input_path = str(vob_files[0])
            else:
                # Create concat file for multiple VOBs
                concat_file = Path(tmpdir) / "concat.txt"
                with open(concat_file, "w") as f:
                    for vob in vob_files:
                        f.write(f"file '{vob}'\n")
                input_path = f"concat:{str(concat_file)}"

            cmd = self.build_ffmpeg_command(input_path, output_path)
            logger.info("Running: %s", " ".join(cmd))

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )

            async for raw_line in proc.stderr:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                seconds = self.parse_time_from_progress(line)
                if seconds is not None and on_progress:
                    pct = self.calculate_progress(seconds, duration)
                    await on_progress(pct)

            await proc.wait()
            success = proc.returncode == 0
            if not success:
                logger.error("FFmpeg exited with code %d", proc.returncode)
            return success

    async def eject(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "eject", self.drive_device,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except Exception:
            logger.exception("Failed to eject disc")
            return False
