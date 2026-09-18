"""Centralized configuration. Secrets only from environment / .env file."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_expiry_minutes: int = 10080

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    socrata_app_token: str = ""
    nyc_lien_endpoint: str = "https://data.cityofnewyork.us/resource/9rz4-mjek.json"

    meili_url: str = "http://127.0.0.1:7700"
    meili_master_key: str = ""
    meili_index: str = "lien_opportunities"

    cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080"
    public_origin: str = "http://localhost:8080"
    enable_hsts: bool = False
    app_env: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_not_placeholder(cls, v: str) -> str:
        if not v or v.startswith("CHANGE_ME"):
            raise ValueError(
                "JWT_SECRET must be set to a real secret "
                '(python -c "import secrets; print(secrets.token_hex(32))")'
            )
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def meili_enabled(self) -> bool:
        return bool(
            self.meili_url
            and self.meili_master_key
            and not self.meili_master_key.startswith("CHANGE_ME")
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
