"""
Centralized configuration.

Fixes a real error from the previous version: `os.environ["DATABASE_URL"]`
raised a bare KeyError with no useful message if the var was missing.
pydantic-settings instead validates all required env vars at startup and
raises one clear error listing exactly what's missing.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    socrata_app_token: str = ""
    nyc_lien_endpoint: str = "https://data.cityofnewyork.us/resource/9rz4-mjek.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Cached so .env is only parsed once per process."""
    return Settings()
