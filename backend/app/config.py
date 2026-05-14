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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
