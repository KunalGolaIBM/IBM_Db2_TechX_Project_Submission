"""
ClaimGuard AI - Backend Configuration
Reads and validates environment variables.
"""

import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve paths
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent.parent
ENV_FILE = PROJECT_DIR / ".env"
EXTERNAL_ENV_FILE = Path("C:/Users/nites/Desktop/kk/claimguard.env")

# Priority order: local .env if present, otherwise external claimguard.env
_active_env_files = [str(f) for f in (ENV_FILE, EXTERNAL_ENV_FILE) if f.is_file()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_active_env_files if _active_env_files else None,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application Info
    APP_NAME: str = "ClaimGuard AI"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    # IBM Db2 Enterprise Configuration
    DB2_HOST: str = "localhost"
    DB2_PORT: int = 50000
    DB2_DATABASE: str = "testdb"
    DB2_USER: str = "db2inst1"
    DB2_PASSWORD: str = ""
    DB2_SCHEMA: str = "CLAIMGUARD"
    DB2_SECURITY: bool = False
    DB2_USE_SSL: bool = False

    # AI & Google Gemini Integration
    GEMINI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"

    # Authentication & Security
    JWT_SECRET: str = "claimguard_dev_secret_key_2026_replace_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    # System Flags & Storage
    DEMO_MODE: bool = True
    UPLOAD_DIR: str = str(PROJECT_DIR / "uploads")

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def db2_connection_string(self) -> str:
        """Constructs an IBM Db2 CLI / ibm_db connection string."""
        security_str = "SECURITY=SSL;" if self.DB2_USE_SSL or self.DB2_SECURITY else ""
        auth_str = "AUTHENTICATION=SERVER;" if not (self.DB2_USE_SSL or self.DB2_SECURITY) else ""
        return (
            f"DATABASE={self.DB2_DATABASE};"
            f"HOSTNAME={self.DB2_HOST};"
            f"PORT={self.DB2_PORT};"
            f"PROTOCOL=TCPIP;"
            f"UID={self.DB2_USER};"
            f"PWD={self.DB2_PASSWORD};"
            f"{auth_str}"
            f"{security_str}"
        )


settings = Settings()
