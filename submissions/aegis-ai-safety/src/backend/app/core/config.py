"""Application configuration loaded exclusively from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the AEGIS API.

    Every value can be overridden through the environment or a local `.env`
    file. No credentials have defaults on purpose: the service must fail loudly
    when the database is not configured rather than silently using a substitute.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- API ---
    aegis_env: str = "development"
    aegis_api_host: str = "0.0.0.0"
    aegis_api_port: int = 8000
    aegis_cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    aegis_max_upload_bytes: int = 10 * 1024 * 1024
    aegis_max_submitted_chars: int = 30_000
    aegis_request_timeout_seconds: int = 600
    aegis_retrieval_backend: str = "lexical"

    # --- IBM Db2 ---
    db2_host: str = "localhost"
    db2_port: int = 50000
    db2_database: str = "TESTDB"
    db2_username: str = "db2inst1"
    db2_password: str = Field(default="")
    db2_schema: str = "AEGIS"

    # --- LLM ---
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = Field(default="")
    llm_base_url: str = ""
    llm_temperature: float = 0.0
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 2
    llm_max_claims: int = 25
    llm_evidence_top_k: int = 6
    llm_max_tokens: int = 1500

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.aegis_cors_origins.split(",") if origin.strip()]

    @property
    def db2_dsn(self) -> str:
        dsn = (
            f"DATABASE={self.db2_database};"
            f"HOSTNAME={self.db2_host};"
            f"PORT={self.db2_port};"
            "PROTOCOL=TCPIP;"
            f"UID={self.db2_username};"
            f"PWD={self.db2_password};"
        )
        if self.aegis_env == "production":
            dsn += "SECURITY=SSL;"
        return dsn


@lru_cache
def get_settings() -> Settings:
    return Settings()
