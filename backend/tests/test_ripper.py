import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from digitizer.ripper import DVDRipper


@pytest.fixture
def ripper():
    return DVDRipper(drive_device="/dev/sr0")


def test_build_ffmpeg_command(ripper):
    cmd = ripper.build_ffmpeg_command(
        title_number=1,
        output_path="/output/dvd/2026-02-09_rip_001.mp4",
    )
    assert "ffmpeg" in cmd[0]
    assert "-i" in cmd
    assert "/output/dvd/2026-02-09_rip_001.mp4" in cmd
    # remux flags - copy, no transcode
    assert "-c" in cmd or "-codec" in cmd
    assert "copy" in cmd


def test_parse_progress_line(ripper):
    line = "frame=  100 fps=30.0 q=-1.0 size=   51200kB time=00:01:30.00 bitrate=4652.8kbits/s speed=2.0x"
    seconds = ripper.parse_time_from_progress(line)
    assert seconds == 90.0


def test_parse_progress_line_no_time(ripper):
    line = "Some random ffmpeg output"
    seconds = ripper.parse_time_from_progress(line)
    assert seconds is None


def test_calculate_progress_percent(ripper):
    pct = ripper.calculate_progress(current_seconds=45.0, total_seconds=90.0)
    assert pct == 50

    pct = ripper.calculate_progress(current_seconds=90.0, total_seconds=90.0)
    assert pct == 100

    pct = ripper.calculate_progress(current_seconds=0.0, total_seconds=90.0)
    assert pct == 0


@patch("digitizer.ripper.asyncio.create_subprocess_exec")
async def test_rip_calls_ffmpeg(mock_exec, ripper):
    mock_proc = AsyncMock()

    async def empty_aiter():
        return
        yield  # make it an async generator

    mock_proc.stderr = empty_aiter()
    mock_proc.wait = AsyncMock(return_value=0)
    mock_proc.returncode = 0
    mock_exec.return_value = mock_proc

    progress_cb = AsyncMock()
    result = await ripper.rip(
        title_number=1,
        duration=100.0,
        output_path="/tmp/test.mp4",
        on_progress=progress_cb,
    )
    assert result is True
    mock_exec.assert_called_once()
