from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_env: str = "development"
    admin_token: str = ""
    database_url: str = "sqlite:///./data/raidshield.db"
    pseudonymization_key: str = ""
    data_encryption_key: str = ""
    store_raw_text: bool = False
    raw_text_retention_hours: int = Field(24, ge=1, le=168)
    aggregate_retention_days: int = Field(30, ge=1, le=365)
    meta_verify_token: str = ""
    meta_app_secret: str = ""
    meta_access_token: str = ""
    meta_ig_user_id: str = ""
    meta_graph_version: str = ""
    frontend_origin: str = "http://localhost:5173"
    fixture_dir: Path = Path(__file__).resolve().parents[2] / "fixtures"

    alert_threshold: float = Field(0.70, ge=0, le=1)
    minimum_unique_authors: int = Field(4, ge=2, le=100)
    similarity_threshold: float = Field(0.85, ge=0.5, le=1)
    cold_start_unique_author_threshold: int = Field(6, ge=2, le=100)
    sync_reference_seconds: float = Field(30, gt=0, le=300)

    @field_validator("frontend_origin")
    @classmethod
    def localhost_origin_in_development(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_security(self) -> Settings:
        if self.app_env not in {"test", "development"}:
            if not self.admin_token or not self.pseudonymization_key:
                raise ValueError(
                    "ADMIN_TOKEN and PSEUDONYMIZATION_KEY are required outside local modes"
                )
            if self.store_raw_text and not self.data_encryption_key:
                raise ValueError("DATA_ENCRYPTION_KEY is required when raw text storage is enabled")
        if self.data_encryption_key:
            try:
                Fernet(self.data_encryption_key.encode())
            except ValueError as exc:
                raise ValueError("DATA_ENCRYPTION_KEY must be a Fernet key") from exc
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
