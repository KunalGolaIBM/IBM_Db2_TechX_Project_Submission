from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List

class Settings(BaseSettings):
    # Application Info
    APP_NAME: str = "Cloud-Loop AI Service"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Shared Internal API Security (between Next.js server handlers and ai-service)
    INTERNAL_API_KEY: str = "cloudloop-internal-key-2026"
    ADMIN_API_KEY: str = "cloudloop-admin-secret-key-2026"

    # Auth mode: 'demo' (zero-account instant evaluation) or 'clerk'
    AUTH_MODE: str = "demo"
    DEMO_USER_ID: str = "demo-student-2026"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://web:3000",
        "https://cloudloop.dev",
    ]

    # IBM Db2 LUW Connection Settings
    DB2_HOST: Optional[str] = None
    DB2_HOSTNAME: Optional[str] = None
    DB2_PORT: int = 50000
    DB2_DB: str = "BLUDB"
    DB2_DATABASE: str = "BLUDB"
    DB2_USERNAME: Optional[str] = None
    DB2_UID: Optional[str] = None
    DB2_PASSWORD: Optional[str] = None
    DB2_PWD: Optional[str] = None
    DB2_SCHEMA: str = "CLOUDLOOP"
    DB2_TABLE_KB: str = "OPPORTUNITY_KB"
    DB2_SSL: bool = False
    DB2_SSL_DSN: Optional[str] = None

    # Local fallback SQLite database path
    LOCAL_DB_PATH: str = "cloud_loop_local.db"

    # Vector & Embedding Model Configurations (MiniLM 384-dim COSINE)
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384
    DISTANCE_METRIC: str = "COSINE"

    # Optional Local LLM via Ollama OpenAI-compatible endpoint
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "llama3.2:latest"

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local", "../.env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def host(self) -> Optional[str]:
        return self.DB2_HOST or self.DB2_HOSTNAME

    @property
    def database_name(self) -> str:
        return self.DB2_DB or self.DB2_DATABASE

    @property
    def username(self) -> Optional[str]:
        return self.DB2_USERNAME or self.DB2_UID

    @property
    def password(self) -> Optional[str]:
        return self.DB2_PASSWORD or self.DB2_PWD

    @property
    def is_db2_configured(self) -> bool:
        return bool(self.host and self.username and self.password) or bool(self.DB2_SSL_DSN)

    @property
    def db2_dsn(self) -> str:
        if self.DB2_SSL_DSN:
            return self.DB2_SSL_DSN
        if not self.host:
            return ""
        dsn = (
            f"DATABASE={self.database_name};"
            f"HOSTNAME={self.host};"
            f"PORT={self.DB2_PORT};"
            f"PROTOCOL=TCPIP;"
            f"UID={self.username};"
            f"PWD={self.password};"
        )
        if self.DB2_SSL:
            dsn += "SECURITY=SSL;"
        return dsn

settings = Settings()
