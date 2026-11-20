from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    secret_key: str
    access_token_expire_minutes: int = 480
    cors_origins: str = "http://localhost:3000"

    # Planning defaults (April-March financial year, priority lead times).
    fy_start_month: int = 4
    lead_time_normal_days: int = 15
    lead_time_urgent_days: int = 10
    lead_time_emergency_days: int = 4

    @field_validator("fy_start_month")
    @classmethod
    def validate_start_month(cls, value: int) -> int:
        if not 1 <= value <= 12:
            raise ValueError("FY_START_MONTH must be between 1 and 12")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
