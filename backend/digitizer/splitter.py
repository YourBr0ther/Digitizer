import asyncio
import logging
import os
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class VideoSplitter:
    def build_split_command(
        self,
        input_path: str,
        start_time: float,
        end_time: float,
        output_path: str,
    ) -> list[str]:
        return [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-ss", f"{start_time:.3f}",
            "-to", f"{end_time:.3f}",
            "-c", "copy",
            "-movflags", "+faststart",
            output_path,
        ]

    async def split_scene(
        self,
        input_path: str,
        start_time: float,
        end_time: float,
        output_path: str,
    ) -> bool:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = self.build_split_command(input_path, start_time, end_time, output_path)
        logger.info("Splitting: %s", " ".join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0

    async def split_all(
        self,
        input_path: str,
        scenes: list[dict],
        output_dir: str,
        on_progress: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> list[str]:
        os.makedirs(output_dir, exist_ok=True)
        output_paths = []

        for i, scene in enumerate(scenes):
            idx = scene["scene_index"]
            output_path = os.path.join(output_dir, f"scene_{idx:03d}.mp4")

            success = await self.split_scene(
                input_path=input_path,
                start_time=scene["start_time"],
                end_time=scene["end_time"],
                output_path=output_path,
            )

            if success:
                output_paths.append(output_path)
            else:
                logger.error("Failed to split scene %d", idx)

            if on_progress:
                pct = int(((i + 1) / len(scenes)) * 100)
                await on_progress(pct, idx)

        return output_paths
