"""Runtime configuration from environment variables and `.env` (see `.env.example`)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    default_provider: str = "ollama"
    default_model: str = "qwen3.5:9b"

    ollama_base_url: str = "http://localhost:11434/v1"
    lmstudio_base_url: str = "http://localhost:1234/v1"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    cli_bridge_url: str = ""
    cli_bridge_token: str = ""

    max_pages: int = 200
    max_upload_mb: int = 100
    batch_chars: int = 6000
    layout_tolerance_pt: float = 5.0
    runs_dir: str = "runs"
    llm_timeout_s: float = 900.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
