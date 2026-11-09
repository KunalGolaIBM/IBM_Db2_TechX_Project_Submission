from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Cloud Loop API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://cloudloop.dev",
    ]

    # IBM Db2 Enterprise
    DB2_HOSTNAME: Optional[str] = None
    DB2_PORT: int = 50000
    DB2_DATABASE: str = "BLUDB"
    DB2_UID: Optional[str] = None
    DB2_PWD: Optional[str] = None
    DB2_SSL: bool = True
    DB2_SSL_DSN: Optional[str] = None

    # Fallback SQLite DB for local sandbox execution when Db2 driver is blocked by OS policy
    LOCAL_DB_PATH: str = "cloud_loop_local.db"

    # Ingestion / Admin Secret
    ADMIN_API_KEY: str = "cloudloop-admin-secret-key-2026"

    # AI & Embeddings
    GOOGLE_AI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local", "../.env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_db2_configured(self) -> bool:
        return bool(self.DB2_HOSTNAME and self.DB2_UID and self.DB2_PWD) or bool(self.DB2_SSL_DSN)

    @property
    def db2_dsn(self) -> str:
        if self.DB2_SSL_DSN:
            return self.DB2_SSL_DSN
        if not self.DB2_HOSTNAME:
            return ""
        dsn = (
            f"DATABASE={self.DB2_DATABASE};"
            f"HOSTNAME={self.DB2_HOSTNAME};"
            f"PORT={self.DB2_PORT};"
            f"PROTOCOL=TCPIP;"
            f"UID={self.DB2_UID};"
            f"PWD={self.DB2_PWD};"
        )
        if self.DB2_SSL:
            dsn += "Security=SSL;"
        return dsn


settings = Settings()

