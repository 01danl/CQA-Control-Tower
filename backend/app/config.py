from decimal import Decimal

from pydantic import SecretStr, field_validator
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
