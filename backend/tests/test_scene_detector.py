import os
import uuid
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from digitizer.scene_detector import SceneDetector


@pytest.fixture
def detector():
    return SceneDetector(
        content_threshold=22.0,
        fade_threshold=12,
        min_scene_length=5.0,
    )


def test_default_thresholds(detector):
    assert detector.content_threshold == 22.0
    assert detector.fade_threshold == 12
    assert detector.min_scene_length == 5.0


def test_filter_short_scenes(detector):
    """Scenes shorter than min_scene_length should be merged with adjacent."""
    raw_scenes = [
        (0.0, 45.0),      # normal scene
        (45.0, 46.5),      # 1.5s - static/noise, should be merged
        (46.5, 120.0),     # normal scene
        (120.0, 121.0),    # 1.0s - static, should be merged
        (121.0, 200.0),    # normal scene
    ]
    filtered = detector.filter_short_scenes(raw_scenes)
    assert len(filtered) == 3
    assert filtered[0] == (0.0, 46.5)   # merged with short scene
    assert filtered[1] == (46.5, 121.0)  # merged with short scene
    assert filtered[2] == (121.0, 200.0)


def test_filter_short_scenes_no_filtering_needed(detector):
    raw_scenes = [
        (0.0, 60.0),
        (60.0, 120.0),
        (120.0, 180.0),
    ]
    filtered = detector.filter_short_scenes(raw_scenes)
    assert len(filtered) == 3


def test_filter_short_scenes_single_scene(detector):
    raw_scenes = [(0.0, 300.0)]
    filtered = detector.filter_short_scenes(raw_scenes)
    assert len(filtered) == 1


def test_build_thumbnail_command(detector):
    cmd = detector.build_thumbnail_command(
        video_path="/input/video.mp4",
        timestamp=45.2,
        output_path="/thumbs/scene_001.jpg",
    )
    assert "ffmpeg" in cmd[0]
    assert "-ss" in cmd
    assert "45.200" in cmd
    assert "/thumbs/scene_001.jpg" in cmd


@patch("digitizer.scene_detector.open_video")
@patch("digitizer.scene_detector.SceneManager")
async def test_analyze_returns_scenes(mock_sm_cls, mock_open_video, detector, tmp_path):
    """Test that analyze calls PySceneDetect and returns scene list."""
    mock_video = MagicMock()
    mock_video.duration = MagicMock(return_value=180.0)
    mock_video.frame_rate = 29.97
    mock_open_video.return_value.__enter__ = MagicMock(return_value=mock_video)
    mock_open_video.return_value.__exit__ = MagicMock(return_value=False)

    mock_sm = MagicMock()
    mock_sm_cls.return_value = mock_sm
    # Simulate PySceneDetect returning scene boundaries
    mock_scene1 = MagicMock()
    mock_scene1.__getitem__ = lambda self, idx: [MagicMock(get_seconds=lambda: 0.0), MagicMock(get_seconds=lambda: 60.0)][idx]
    mock_scene2 = MagicMock()
    mock_scene2.__getitem__ = lambda self, idx: [MagicMock(get_seconds=lambda: 60.0), MagicMock(get_seconds=lambda: 180.0)][idx]
    mock_sm.get_scene_list.return_value = [mock_scene1, mock_scene2]

    thumb_dir = str(tmp_path / "thumbs")
    with patch.object(detector, "_extract_thumbnail", new_callable=AsyncMock) as mock_thumb:
        mock_thumb.return_value = True
        scenes = await detector.analyze(
            video_path="/input/video.mp4",
            thumbnail_dir=thumb_dir,
        )

    assert len(scenes) == 2
    assert scenes[0]["start_time"] == 0.0
    assert scenes[0]["end_time"] == 60.0
    assert scenes[1]["start_time"] == 60.0
    assert scenes[1]["end_time"] == 180.0
