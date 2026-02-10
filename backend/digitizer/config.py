from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    output_base_path: str = "/output/dvd"
    vhs_output_path: str = "/output/vhs"
    naming_pattern: str = "YYYY-MM-DD_rip_NNN"
    auto_eject: bool = True
    drive_device: str = "/dev/sr0"
    capture_device: str = "/dev/video0"
    poll_interval: float = 2.0
    db_path: str = "/data/digitizer.db"
    encoding_preset: str = "fast"
    crf_quality: int = 23
    audio_bitrate: str = "192k"

    model_config = {"env_prefix": "DIGITIZER_"}


settings = Settings()
