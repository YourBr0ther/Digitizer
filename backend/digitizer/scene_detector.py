import asyncio
import logging
import os
import uuid
from collections.abc import Awaitable, Callable

from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector, ThresholdDetector

logger = logging.getLogger(__name__)


class SceneDetector:
    def __init__(
        self,
        content_threshold: float = 22.0,
        fade_threshold: int = 12,
        min_scene_length: float = 5.0,
    ):
        self.content_threshold = content_threshold
        self.fade_threshold = fade_threshold
        self.min_scene_length = min_scene_length

    def filter_short_scenes(
        self, scenes: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        if len(scenes) <= 1:
            return scenes

        filtered = []
        i = 0
        while i < len(scenes):
            start, end = scenes[i]
            duration = end - start
            if duration < self.min_scene_length and filtered:
                # Merge short scene into previous
                prev_start, _ = filtered[-1]
                filtered[-1] = (prev_start, end)
            elif duration < self.min_scene_length and i + 1 < len(scenes):
                # Merge short scene into next
                next_start, next_end = scenes[i + 1]
                scenes[i + 1] = (start, next_end)
            else:
                filtered.append((start, end))
            i += 1
        return filtered

    def build_thumbnail_command(
        self, video_path: str, timestamp: float, output_path: str
    ) -> list[str]:
        return [
            "ffmpeg",
            "-y",
            "-ss", f"{timestamp:.3f}",
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            output_path,
        ]

    async def _extract_thumbnail(
        self, video_path: str, timestamp: float, output_path: str
    ) -> bool:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = self.build_thumbnail_command(video_path, timestamp, output_path)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0

    async def analyze(
        self,
        video_path: str,
        thumbnail_dir: str,
        on_progress: Callable[[int], Awaitable[None]] | None = None,
    ) -> list[dict]:
        if on_progress:
            await on_progress(0)

        # Run PySceneDetect (CPU-bound, run in thread)
        raw_scenes = await asyncio.to_thread(
            self._detect_scenes, video_path
        )

        if on_progress:
            await on_progress(50)

        # Filter short scenes (static/noise)
        filtered = self.filter_short_scenes(raw_scenes)

        # Extract thumbnails
        scenes = []
        for i, (start, end) in enumerate(filtered):
            scene_index = i + 1
            thumb_path = os.path.join(thumbnail_dir, f"scene_{scene_index:03d}.jpg")

            # Extract thumbnail at the start of each scene (offset by 0.5s for better frame)
            thumb_time = start + 0.5 if start + 0.5 < end else start
            await self._extract_thumbnail(video_path, thumb_time, thumb_path)

            scenes.append({
                "id": str(uuid.uuid4()),
                "scene_index": scene_index,
                "start_time": start,
                "end_time": end,
                "duration": round(end - start, 3),
                "thumbnail_path": thumb_path,
            })

            if on_progress:
                pct = 50 + int((scene_index / len(filtered)) * 50)
                await on_progress(min(pct, 100))

        return scenes

    def _detect_scenes(self, video_path: str) -> list[tuple[float, float]]:
        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=self.content_threshold))
        scene_manager.add_detector(ThresholdDetector(threshold=self.fade_threshold))
        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()

        if not scene_list:
            # No cuts detected - entire video is one scene
            duration = video.duration.get_seconds()
            return [(0.0, duration)]

        return [
            (scene[0].get_seconds(), scene[1].get_seconds())
            for scene in scene_list
        ]
