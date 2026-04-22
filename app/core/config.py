"""
Application configuration management.

Uses Pydantic Settings to load and validate configuration from
environment variables and `.env` files. All ML thresholds and Flask
parameters live here and can be overridden via environment.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Flask ---
    flask_env: Literal["development", "staging", "production"] = "development"
    flask_debug: bool = True
    secret_key: str = Field(default="dev-secret-key-change-in-production", min_length=16)
    host: str = "0.0.0.0"
    port: int = 5000

    # --- API ---
    api_prefix: str = "/api/v1"
    api_rate_limit: str = "100 per minute"
    cors_origins: str = "*"

    # --- Logging ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    # --- ML: Anomaly Detection ---
    anomaly_contamination: float = Field(default=0.05, ge=0.001, le=0.5)
    anomaly_random_state: int = 42

    # --- ML: Health Scoring weights (must sum to 1.0) ---
    health_score_weights_util: float = 0.30
    health_score_weights_errors: float = 0.30
    health_score_weights_discards: float = 0.25
    health_score_weights_anomaly: float = 0.15

    # --- Thresholds ---
    util_warning_threshold: float = 70.0
    util_critical_threshold: float = 90.0
    error_warning_threshold: int = 10
    error_critical_threshold: int = 100
    discard_warning_threshold: int = 50
    discard_critical_threshold: int = 500

    # --- File handling ---
    max_upload_mb: int = 50
    data_dir: Path = Path("./data")

    @field_validator("data_dir")
    @classmethod
    def _ensure_data_dir(cls, v: Path) -> Path:
        v = Path(v)
        (v / "input").mkdir(parents=True, exist_ok=True)
        (v / "output").mkdir(parents=True, exist_ok=True)
        (v / "models").mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("health_score_weights_anomaly")
    @classmethod
    def _check_weights_sum(cls, v: float, info) -> float:
        # Validate weights total ≈ 1.0 once the last weight is being parsed.
        data = info.data
        total = (
            data.get("health_score_weights_util", 0)
            + data.get("health_score_weights_errors", 0)
            + data.get("health_score_weights_discards", 0)
            + v
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Health score weights must sum to 1.0 (got {total:.3f})"
            )
        return v

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.flask_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (one per process)."""
    return Settings()
