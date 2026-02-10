import asyncio
import logging
import re

from digitizer.models import DriveStatus

logger = logging.getLogger(__name__)

TITLE_PATTERN = re.compile(
    r"Title:\s*(\d+),\s*Length:\s*(\d{2}):(\d{2}):(\d{2})"
)
LONGEST_PATTERN = re.compile(r"Longest track:\s*(\d+)")


class DriveMonitor:
    def __init__(self, device: str = "/dev/sr0"):
        self.device = device
        self.status = DriveStatus.EMPTY
        self._disc_present = False

    async def check_disc(self) -> dict | None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "lsdvd", self.device,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                return None
            return self.parse_lsdvd(stdout.decode("utf-8", errors="replace"))
        except Exception:
            logger.exception("Error checking disc")
            return None

    def parse_lsdvd(self, output: str) -> dict:
        titles = []
        for match in TITLE_PATTERN.finditer(output):
            num = int(match.group(1))
            h, m, s = int(match.group(2)), int(match.group(3)), int(match.group(4))
            duration = h * 3600 + m * 60 + s
            titles.append({"number": num, "duration": float(duration)})

        longest_match = LONGEST_PATTERN.search(output)
        main_title = int(longest_match.group(1)) if longest_match else (
            max(titles, key=lambda t: t["duration"])["number"] if titles else 1
        )

        main_duration = next(
            (t["duration"] for t in titles if t["number"] == main_title), 0.0
        )

        return {
            "title_count": len(titles),
            "main_title": main_title,
            "duration": main_duration,
        }

    async def poll_once(self) -> tuple[DriveStatus, dict | None]:
        disc_info = await self.check_disc()
        old_status = self.status

        if disc_info is not None and not self._disc_present:
            self._disc_present = True
            self.status = DriveStatus.DISC_DETECTED
            return self.status, disc_info
        elif disc_info is None and self._disc_present:
            self._disc_present = False
            self.status = DriveStatus.EMPTY
            return self.status, None

        return old_status, None

    def set_ripping(self):
        self.status = DriveStatus.RIPPING

    def set_empty(self):
        self.status = DriveStatus.EMPTY
        self._disc_present = False
