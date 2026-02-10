from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    output_base_path: str = "/output/dvd"
    naming_pattern: str = "YYYY-MM-DD_rip_NNN"
    auto_eject: bool = True
    drive_device: str = "/dev/sr0"
    poll_interval: float = 2.0
    db_path: str = "/data/digitizer.db"

    model_config = {"env_prefix": "DIGITIZER_"}


settings = Settings()
