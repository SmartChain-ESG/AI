from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # OpenAI
    openai_api_key: str
    openai_base_url: str | None = None

    # Models
    openai_model_light: str = "gpt-4o-mini"
    openai_model_heavy: str = "gpt-5.1"
    openai_embedding_model: str = "text-embedding-3-small"

    # Vector DB (CHATBOT_ prefix)
    chroma_path: str = Field(
        default="apps/chatbot_api/app/vectordb",
        validation_alias="CHATBOT_CHROMA_PATH"
    )
    chroma_collection: str = Field(
        default="hd_hhi_compliance_kb",
        validation_alias="CHATBOT_CHROMA_COLLECTION"
    )

    # Admin 보호
    admin_api_key: str


settings = Settings()