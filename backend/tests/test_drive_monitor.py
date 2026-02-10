import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from digitizer.drive_monitor import DriveMonitor
from digitizer.models import DriveStatus


@pytest.fixture
def monitor():
    return DriveMonitor(device="/dev/sr0")


def test_initial_status_is_empty(monitor):
    assert monitor.status == DriveStatus.EMPTY


LSDVD_OUTPUT = """Disc Title: UNKNOWN
Title: 01, Length: 01:30:00.000 Chapters: 01, Cells: 01, Audio streams: 01, Subpictures: 00
Longest track: 01
"""


@patch("digitizer.drive_monitor.asyncio.create_subprocess_exec")
async def test_check_disc_detected(mock_exec, monitor):
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(LSDVD_OUTPUT.encode(), b""))
    mock_proc.returncode = 0
    mock_exec.return_value = mock_proc

    result = await monitor.check_disc()
    assert result is not None
    assert result["main_title"] == 1
    assert result["duration"] == 5400.0


@patch("digitizer.drive_monitor.asyncio.create_subprocess_exec")
async def test_check_disc_empty(mock_exec, monitor):
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))
    mock_proc.returncode = 1
    mock_exec.return_value = mock_proc

    result = await monitor.check_disc()
    assert result is None


def test_parse_lsdvd_output(monitor):
    info = monitor.parse_lsdvd(LSDVD_OUTPUT)
    assert info["title_count"] == 1
    assert info["main_title"] == 1
    assert info["duration"] == 5400.0
