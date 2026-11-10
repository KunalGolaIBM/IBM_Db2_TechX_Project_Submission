from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BLACKSTART AI"
    app_version: str = "1.0.0"
    environment: str = "development"
    db2_dsn: str = ""
    # Comma-separated browser origins allowed by CORS.
    # Default "*" preserves local development; production should set e.g.
    # CORS_ORIGINS=https://your-frontend.onrender.com
    cors_origins: str = "*"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


def parse_cors_origins(raw: str) -> list[str]:
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
