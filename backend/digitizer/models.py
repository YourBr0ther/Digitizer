from enum import Enum

from pydantic import BaseModel


class JobStatus(str, Enum):
    DETECTED = "detected"
    RIPPING = "ripping"
    COMPLETE = "complete"
    FAILED = "failed"


class DriveStatus(str, Enum):
    EMPTY = "empty"
    DISC_DETECTED = "disc_detected"
    RIPPING = "ripping"


class CaptureStatus(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"


class DiscInfo(BaseModel):
    title_count: int = 0
    main_title: int = 1
    duration: float = 0.0


class Job(BaseModel):
    id: str
    source_type: str = "dvd"
    disc_info: DiscInfo = DiscInfo()
    status: JobStatus = JobStatus.DETECTED
    progress: int = 0
    output_path: str | None = None
    file_size: int | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None


class Settings(BaseModel):
    output_path: str = "/output/dvd"
    naming_pattern: str = "YYYY-MM-DD_rip_NNN"
    auto_eject: bool = True


class WSEvent(BaseModel):
    event: str
    data: dict
