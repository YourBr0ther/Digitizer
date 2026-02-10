import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from digitizer.splitter import VideoSplitter


@pytest.fixture
def splitter():
    return VideoSplitter()


def test_build_split_command(splitter):
    cmd = splitter.build_split_command(
        input_path="/input/video.mp4",
        start_time=45.2,
        end_time=120.5,
        output_path="/output/scene_001.mp4",
    )
    assert "ffmpeg" in cmd[0]
    assert "-ss" in cmd
    assert "-to" in cmd or "-t" in cmd
    assert "-c" in cmd
    assert "copy" in cmd
    assert "/output/scene_001.mp4" in cmd


def test_build_split_command_from_start(splitter):
    cmd = splitter.build_split_command(
        input_path="/input/video.mp4",
        start_time=0.0,
        end_time=60.0,
        output_path="/output/scene_001.mp4",
    )
    assert "-ss" in cmd
    assert "0.000" in cmd or "0" in cmd


@patch("digitizer.splitter.asyncio.create_subprocess_exec")
async def test_split_single_scene(mock_exec, splitter):
    mock_proc = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mock_proc.returncode = 0
    mock_exec.return_value = mock_proc

    result = await splitter.split_scene(
        input_path="/input/video.mp4",
        start_time=0.0,
        end_time=60.0,
        output_path="/output/scene_001.mp4",
    )
    assert result is True


@patch("digitizer.splitter.asyncio.create_subprocess_exec")
async def test_split_all(mock_exec, splitter, tmp_path):
    mock_proc = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mock_proc.returncode = 0
    mock_exec.return_value = mock_proc

    scenes = [
        {"scene_index": 1, "start_time": 0.0, "end_time": 60.0},
        {"scene_index": 2, "start_time": 60.0, "end_time": 120.0},
        {"scene_index": 3, "start_time": 120.0, "end_time": 180.0},
    ]
    progress_cb = AsyncMock()
    output_dir = str(tmp_path / "scenes")

    paths = await splitter.split_all(
        input_path="/input/video.mp4",
        scenes=scenes,
        output_dir=output_dir,
        on_progress=progress_cb,
    )
    assert len(paths) == 3
    assert all("scene_" in p for p in paths)
    assert progress_cb.call_count >= 3


@patch("digitizer.splitter.asyncio.create_subprocess_exec")
async def test_split_scene_failure(mock_exec, splitter):
    mock_proc = AsyncMock()
    mock_proc.wait = AsyncMock(return_value=1)
    mock_proc.returncode = 1
    mock_exec.return_value = mock_proc

    result = await splitter.split_scene(
        input_path="/input/video.mp4",
        start_time=0.0,
        end_time=60.0,
        output_path="/output/scene_001.mp4",
    )
    assert result is False
