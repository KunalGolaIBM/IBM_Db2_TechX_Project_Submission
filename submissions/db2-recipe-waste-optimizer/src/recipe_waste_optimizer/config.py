"""Application configuration."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Settings
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str = "dev_secret_key_change_in_production"
    FRONTEND_URL: str = "http://localhost:5173"

    # IBM Db2 Database Configuration
    DB2_HOST: str = "localhost"
    DB2_PORT: int = 50000
    DB2_DATABASE: str = "testdb"
    DB2_USERNAME: str = "db2inst1"
    DB2_PASSWORD: str = "Db2Hack2026!"
    DB2_SCHEMA: str = "DB2INST1"
    DB2_SSL: bool = False

    # AI / LLM Configuration
    LLM_PROVIDER: str = "openrouter"  # openrouter, mock, or openai
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "meta-llama/llama-3.3-70b-instruct:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Embeddings Configuration
    EMBEDDING_PROVIDER: str = "local"  # local or hash
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # Default Household ID for single-user hackathon demo
    DEFAULT_HOUSEHOLD_ID: str = "household_demo_01"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def db2_connection_string(self) -> str:
        """Construct raw connection string for ibm_db driver."""
        ssl_str = "SECURITY=SSL;" if self.DB2_SSL else ""
        return (
            f"DATABASE={self.DB2_DATABASE};"
            f"HOSTNAME={self.DB2_HOST};"
            f"PORT={self.DB2_PORT};"
            f"PROTOCOL=TCPIP;"
            f"UID={self.DB2_USERNAME};"
            f"PWD={self.DB2_PASSWORD};"
            f"AUTHENTICATION=SERVER;"
            f"{ssl_str}"
        )


settings = Settings()
