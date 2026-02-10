import asyncio
import logging
import os
import re
import signal
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

TIME_PATTERN = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")


class VHSCapture:
    def __init__(
        self,
        capture_device: str = "/dev/video0",
        encoding_preset: str = "fast",
        crf_quality: int = 23,
        audio_bitrate: str = "192k",
    ):
        self.capture_device = capture_device
        self.encoding_preset = encoding_preset
        self.crf_quality = crf_quality
        self.audio_bitrate = audio_bitrate
        self._recording = False
        self._process: asyncio.subprocess.Process | None = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def current_process(self) -> asyncio.subprocess.Process | None:
        return self._process

    def build_ffmpeg_command(self, output_path: str) -> list[str]:
        return [
            "ffmpeg",
            "-y",
            "-f", "v4l2",
            "-i", self.capture_device,
            "-c:v", "libx264",
            "-preset", self.encoding_preset,
            "-crf", str(self.crf_quality),
            "-c:a", "aac",
            "-b:a", self.audio_bitrate,
            "-movflags", "+faststart",
            output_path,
        ]

    def parse_elapsed_time(self, line: str) -> float | None:
        match = TIME_PATTERN.search(line)
        if not match:
            return None
        h, m, s, cs = match.groups()
        return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100

    async def start(
        self,
        output_path: str,
        on_progress: Callable[[float, int], Awaitable[None]] | None = None,
    ) -> bool:
        if self._recording:
            raise RuntimeError("Already recording")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = self.build_ffmpeg_command(output_path)
        logger.info("Starting capture: %s", " ".join(cmd))

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        self._recording = True

        try:
            async for raw_line in self._process.stderr:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                elapsed = self.parse_elapsed_time(line)
                if elapsed is not None and on_progress:
                    file_size = 0
                    if os.path.exists(output_path):
                        try:
                            file_size = os.path.getsize(output_path)
                        except OSError:
                            pass
                    await on_progress(elapsed, file_size)

            await self._process.wait()
            success = self._process.returncode == 0 or self._process.returncode == -2  # SIGINT
            return success
        finally:
            self._recording = False
            self._process = None

    async def stop(self):
        if not self._recording or self._process is None:
            raise RuntimeError("Not recording")

        logger.info("Stopping capture (SIGINT to pid %d)", self._process.pid)
        self._process.send_signal(signal.SIGINT)
        await self._process.wait()
        self._recording = False
