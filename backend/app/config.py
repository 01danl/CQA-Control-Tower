from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            Path(__file__).resolve().parents[2] / ".env",
            Path(__file__).resolve().parents[1] / ".env",
        ),
        extra="ignore",
        populate_by_name=True,
    )

    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://cqa:cqa-local-placeholder@localhost:55432/cqa"
    )
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    cqa_dataset_url: SecretStr | None = None
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"),
    )
    llm_model: str | None = "deepseek/deepseek-v4.1-flash"
    # None preserves the provider default; changes require a new approved run plan.
    llm_reasoning_effort: Literal["max", "high", "low", "none"] | None = None
    llm_max_output_tokens: int = Field(default=8192, ge=1024, le=32768)
    llm_input_price_usd_per_1m: Decimal | None = None
    llm_output_price_usd_per_1m: Decimal | None = None
    openai_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL"),
    )
    dataset_timeout_seconds: float = Field(default=15, gt=0, le=120)
    llm_timeout_seconds: float = Field(default=30, gt=0, le=120)
    http_retries: int = Field(default=2, ge=0, le=3)
    retry_backoff_seconds: float = Field(default=0.5, ge=0, le=5)
    max_retry_delay_seconds: float = Field(default=5, ge=0, le=60)
    batch_concurrency: int = Field(default=2, ge=1, le=8)
    max_pending_evaluations: int = Field(default=1000, ge=1, le=10000)
    worker_poll_seconds: float = Field(default=0.5, gt=0, le=10)

    @field_validator("llm_reasoning_effort", mode="before")
    @classmethod
    def blank_effort_preserves_provider_default(cls, value):
        return None if value == "" else value

    @field_validator("llm_model", mode="before")
    @classmethod
    def blank_model_uses_default(cls, value):
        return (
            "deepseek/deepseek-v4.1-flash"
            if isinstance(value, str) and not value.strip()
            else value
        )

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
