"""Configuration settings for SplitSync AI backend."""

from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Db2
    db2_host: str = "localhost"
    db2_port: int = 50000
    db2_database: str = "splitsync"
    db2_user: str = "db2inst1"
    db2_password: str = ""
    db2_schema: str = "SPLITSYNC"

    # App
    app_env: str = "development"
    app_port: int = 8000
    app_secret_key: str = "change-me-in-production-min-32-chars"
    app_cors_origins: str = "http://localhost:3000"

    # JWT
    jwt_secret: str = "change-me-in-production-min-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 1440

    # AI
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ai_provider: str = "openai"
    ai_model: str = "gpt-4o-mini"

    # Payment
    payment_mode: str = "demo"
    demo_upi_id: str = "splitsync-demo@upi"

    @property
    def db2_connection_string(self) -> str:
        return (
            f"DATABASE={self.db2_database};"
            f"HOSTNAME={self.db2_host};"
            f"PORT={self.db2_port};"
            f"PROTOCOL=TCPIP;"
            f"UID={self.db2_user};"
            f"PWD={self.db2_password};"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.app_cors_origins.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
