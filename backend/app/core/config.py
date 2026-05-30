from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Worknoon Refund Agent"
    database_url: str = "sqlite:///./data/worknoon_refunds.db"
    business_today: str = "2026-06-01"
    frontend_origin: str = "http://localhost:3000"

    llm_provider: str = Field(default="gemini", pattern="^(gemini|groq|openai|mock)$")
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    seed_data_path: Path = Path(__file__).resolve().parents[1] / "data" / "synthetic_crm.json"
    policy_path: Path = Path(__file__).resolve().parents[1] / "data" / "refund_policy.md"


@lru_cache
def get_settings() -> Settings:
    return Settings()
