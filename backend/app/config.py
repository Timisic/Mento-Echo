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
    admin_password: str = Field(default="echo2026", alias="ADMIN_PASSWORD")
    admin_token: str = Field(default="dev-admin-token-change-me", alias="ADMIN_TOKEN")
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    ai_provider_name: str = Field(default="mock", alias="AI_PROVIDER_NAME")
    ai_base_url: str = Field(default="https://api.openai.com/v1", alias="AI_BASE_URL")
    ai_api_key: str | None = Field(default=None, alias="AI_API_KEY")
    ai_model_name: str = Field(default="mock-mentor-echo", alias="AI_MODEL_NAME")
    ai_temperature: float = Field(default=0.3, alias="AI_TEMPERATURE")
    ai_max_tokens: int = Field(default=600, alias="AI_MAX_TOKENS")
    ai_timeout_seconds: float = Field(default=10.0, alias="AI_TIMEOUT_SECONDS")
    ai_response_sla_seconds: float = Field(default=30.0, alias="AI_RESPONSE_SLA_SECONDS")
    ai_fallback_enabled: bool = Field(default=True, alias="AI_FALLBACK_ENABLED")
    ai_fallback_provider_name: str = Field(default="deepseek", alias="AI_FALLBACK_PROVIDER_NAME")
    ai_fallback_base_url: str = Field(default="https://api.deepseek.com", alias="AI_FALLBACK_BASE_URL")
    ai_fallback_api_key: str | None = Field(default=None, alias="AI_FALLBACK_API_KEY")
    ai_fallback_model_name: str = Field(default="deepseek-v4-flash", alias="AI_FALLBACK_MODEL_NAME")
    ai_fallback_temperature: float = Field(default=0.3, alias="AI_FALLBACK_TEMPERATURE")
    ai_fallback_max_tokens: int = Field(default=800, alias="AI_FALLBACK_MAX_TOKENS")
    ai_fallback_timeout_seconds: float = Field(default=30.0, alias="AI_FALLBACK_TIMEOUT_SECONDS")
    ai_fallback_max_attempts: int = Field(default=2, alias="AI_FALLBACK_MAX_ATTEMPTS")
    study_mode: str = Field(default="pilot_single", alias="STUDY_MODE")
    self_registration_enabled: bool = Field(default=True, alias="SELF_REGISTRATION_ENABLED")
    participant_code_prefix: str = Field(default="P", alias="PARTICIPANT_CODE_PREFIX")
    codex_command: str = Field(default="codex app-server --disable hooks", alias="CODEX_COMMAND")
    codex_approval_policy: str = Field(default="never", alias="CODEX_APPROVAL_POLICY")
    codex_sandbox: str = Field(default="read-only", alias="CODEX_SANDBOX")
    codex_reasoning_effort: str = Field(default="low", alias="CODEX_REASONING_EFFORT")
    codex_read_timeout_seconds: float = Field(default=2.0, alias="CODEX_READ_TIMEOUT_SECONDS")
    codex_turn_timeout_seconds: float = Field(default=25.0, alias="CODEX_TURN_TIMEOUT_SECONDS")
    codex_cwd: str | None = Field(default=None, alias="CODEX_CWD")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
