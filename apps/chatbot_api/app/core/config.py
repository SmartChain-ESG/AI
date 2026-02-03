from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # OpenAI
    openai_api_key: str
    openai_base_url: str | None = None

    # Models
    openai_model_light: str = "gpt-4o-mini"
    openai_model_heavy: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    # Vector DB
    chroma_path: str = "apps/chatbot_api/app/vectordb"
    chroma_collection: str = "hd_hhi_compliance_kb"

    # Admin 보호
    admin_api_key: str = "change-me"


settings = Settings()