"""Application Configuration."""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Core CloudChange configuration settings."""
    model_config = SettingsConfigDict(env_prefix="CLOUDCHANGE_", extra="ignore")

    PROJECT_NAME: str = "CloudChange"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    DEFAULT_AWS_REGION: str = "us-east-1"
    DEBUG: bool = False

    # Persistence Backend: 'memory' (default for isolated tests) or 'db2' (IBM Db2 enterprise storage)
    DATABASE_BACKEND: str = os.getenv("DATABASE_BACKEND") or os.getenv("CLOUDCHANGE_DATABASE_BACKEND", "memory")

    # Db2 Configuration Options
    DB2_HOST: str = os.getenv("DB2_HOST") or os.getenv("DB2_HOSTNAME", "localhost")
    DB2_PORT: int = int(os.getenv("DB2_PORT", "50000"))
    DB2_DATABASE: str = os.getenv("DB2_DATABASE") or os.getenv("DB2_DB", "BLUDB")
    DB2_USER: str = os.getenv("DB2_USER") or os.getenv("DB2_UID", "db2inst1")
    DB2_PASSWORD: str = os.getenv("DB2_PASSWORD") or os.getenv("DB2_PWD", "")
    DB2_SECURITY: str = os.getenv("DB2_SECURITY", "")
    DB2_SCHEMA: str = os.getenv("DB2_SCHEMA", "CLOUDCHANGE")


settings = Settings()
