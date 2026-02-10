import asyncio
import signal
from unittest.mock import AsyncMock, patch, MagicMock, PropertyMock

import pytest

from digitizer.capture import VHSCapture


@pytest.fixture
def capture():
    return VHSCapture(
        capture_device="/dev/video0",
        encoding_preset="fast",
        crf_quality=23,
        audio_bitrate="192k",
    )


def test_initial_state_is_idle(capture):
    assert capture.is_recording is False
    assert capture.current_process is None


def test_build_ffmpeg_command(capture):
    cmd = capture.build_ffmpeg_command(output_path="/output/vhs/test.mp4")
    assert "ffmpeg" in cmd[0]
    assert "-f" in cmd
    assert "v4l2" in cmd
    assert "/dev/video0" in cmd
    assert "-c:v" in cmd
    assert "libx264" in cmd
    assert "-preset" in cmd
    assert "fast" in cmd
    assert "-crf" in cmd
    assert "23" in cmd
    assert "-c:a" in cmd
    assert "aac" in cmd
    assert "/output/vhs/test.mp4" in cmd


def test_build_ffmpeg_command_custom_preset(capture):
    capture.encoding_preset = "medium"
    capture.crf_quality = 20
    cmd = capture.build_ffmpeg_command(output_path="/output/vhs/test.mp4")
    assert "medium" in cmd
    assert "20" in cmd


def test_parse_elapsed_time(capture):
    line = "frame=  100 fps=30.0 q=28.0 size=   5120kB time=00:05:30.00 bitrate=1234.5kbits/s speed=1.0x"
    seconds = capture.parse_elapsed_time(line)
    assert seconds == 330.0


def test_parse_elapsed_time_no_match(capture):
    line = "Some random output"
    seconds = capture.parse_elapsed_time(line)
    assert seconds is None


@patch("digitizer.capture.asyncio.create_subprocess_exec")
async def test_start_recording(mock_exec, capture):
    mock_proc = AsyncMock()
    mock_proc.pid = 12345
    mock_proc.stderr = AsyncMock()
    # Mock the async iterator to just complete immediately
    mock_proc.stderr.__aiter__ = lambda self: self
    mock_proc.stderr.__anext__ = AsyncMock(side_effect=StopAsyncIteration)
    mock_proc.wait = AsyncMock(return_value=0)
    mock_proc.returncode = 0
    mock_exec.return_value = mock_proc

    progress_cb = AsyncMock()
    result = await capture.start(
        output_path="/tmp/test.mp4",
        on_progress=progress_cb,
    )
    assert result is True
    mock_exec.assert_called_once()


async def test_start_while_recording_raises(capture):
    capture._recording = True
    with pytest.raises(RuntimeError, match="Already recording"):
        await capture.start(output_path="/tmp/test.mp4")


@patch("digitizer.capture.asyncio.create_subprocess_exec")
async def test_stop_recording(mock_exec, capture):
    mock_proc = AsyncMock()
    mock_proc.pid = 12345
    mock_proc.send_signal = MagicMock()
    mock_proc.wait = AsyncMock(return_value=0)
    mock_proc.returncode = 0

    capture._recording = True
    capture._process = mock_proc

    await capture.stop()
    mock_proc.send_signal.assert_called_once_with(signal.SIGINT)
    assert capture._recording is False


async def test_stop_while_not_recording_raises(capture):
    with pytest.raises(RuntimeError, match="Not recording"):
        await capture.stop()
