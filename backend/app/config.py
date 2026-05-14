from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(
        default="postgresql+pg8000://mentor_echo:mentor_echo@localhost:5432/mentor_echo",
        alias="DATABASE_URL",
    )
    admin_username: str = Field(default="researcher", alias="ADMIN_USERNAME")
    admin_password: str = Field(default="change-me-admin-password", alias="ADMIN_PASSWORD")
    admin_token: str = Field(default="dev-admin-token-change-me", alias="ADMIN_TOKEN")
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    ai_provider_name: str = Field(default="mock", alias="AI_PROVIDER_NAME")
    ai_base_url: str = Field(default="https://api.openai.com/v1", alias="AI_BASE_URL")
    ai_api_key: str | None = Field(default=None, alias="AI_API_KEY")
    ai_model_name: str = Field(default="mock-mentor-echo", alias="AI_MODEL_NAME")
    ai_temperature: float = Field(default=0.3, alias="AI_TEMPERATURE")
    ai_max_tokens: int = Field(default=600, alias="AI_MAX_TOKENS")
    ai_timeout_seconds: float = Field(default=30.0, alias="AI_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
