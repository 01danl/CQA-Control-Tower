from decimal import Decimal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://cqa:cqa-local-placeholder@localhost:55432/cqa"
    )
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    cqa_dataset_url: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_input_price_usd_per_1m: Decimal | None = None
    llm_output_price_usd_per_1m: Decimal | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    dataset_timeout_seconds: float = Field(default=15, gt=0, le=120)
    llm_timeout_seconds: float = Field(default=30, gt=0, le=120)
    http_retries: int = Field(default=2, ge=0, le=3)
    retry_backoff_seconds: float = Field(default=0.5, ge=0, le=5)
    batch_concurrency: int = Field(default=2, ge=1, le=8)
    max_pending_evaluations: int = Field(default=1000, ge=1, le=10000)
    worker_poll_seconds: float = Field(default=0.5, gt=0, le=10)

    @field_validator("llm_input_price_usd_per_1m", "llm_output_price_usd_per_1m", mode="before")
    @classmethod
    def blank_price_is_unconfigured(cls, value):
        return None if value == "" else value

    @field_validator("cors_origins")
    @classmethod
    def explicit_origins_only(cls, value):
        if "*" in value:
            raise ValueError("Configure explicit CORS origins")
        return value

    @field_validator("llm_input_price_usd_per_1m", "llm_output_price_usd_per_1m")
    @classmethod
    def nonnegative_prices(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or value < 0):
            raise ValueError("Price must be a finite nonnegative decimal")
        return value
