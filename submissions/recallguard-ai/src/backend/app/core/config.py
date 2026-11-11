"""Application settings, read from environment variables / .env (never hard-coded secrets)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", BACKEND_DIR.parents[1] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "RecallGuard AI"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- database -------------------------------------------------------
    # db2  -> IBM Db2 via ibm_db (system of record)
    # dev  -> embedded engine executing the SAME SQL files; clearly labelled
    #         "DEV MODE — NOT IBM Db2" in /health and in the UI banner.
    db_mode: Literal["db2", "dev"] = "dev"
    db2_host: str = "localhost"
    db2_port: int = 50000
    db2_database: str = "RECALLDB"
    db2_user: str = "db2inst1"
    db2_password: str = Field(default="", repr=False)
    db2_security: str = ""  # set to SSL for Db2 on Cloud
    db2_schema: str = ""
    dev_db_path: str = str(BACKEND_DIR / "data" / "recallguard_dev.sqlite")
    auto_migrate: bool = True
    auto_seed: bool = True

    # ---- AI ---------------------------------------------------------------
    # none -> deterministic fallback agents (clearly labelled, never presented as LLM output)
    llm_provider: Literal["none", "openai", "watsonx", "ollama", "anthropic", "gemini"] = "none"
    llm_model: str = ""
    llm_base_url: str = ""
    llm_temperature: float = 0.1
    openai_api_key: str = Field(default="", repr=False)
    anthropic_api_key: str = Field(default="", repr=False)
    gemini_api_key: str = Field(default="", repr=False)
    watsonx_apikey: str = Field(default="", repr=False)
    watsonx_project_id: str = ""
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"

    # ---- retrieval ------------------------------------------------------
    embedding_provider: Literal["hashing", "openai"] = "hashing"
    embedding_dim: int = 256
    vector_table: str = "RG_EVIDENCE_VECTORS"

    # ---- uploads / security -------------------------------------------
    upload_dir: str = str(BACKEND_DIR / "data" / "uploads")
    max_upload_mb: int = 10
    require_auth_headers: bool = False

    # ---- risk ---------------------------------------------------------
    risk_config_path: str = str(BACKEND_DIR / "app" / "core" / "risk_config.json")

    @property
    def llm_configured(self) -> bool:
        if self.llm_provider == "none":
            return False
        if self.llm_provider == "ollama":
            return bool(self.llm_model)
        key = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "gemini": self.gemini_api_key,
            "watsonx": self.watsonx_apikey,
        }.get(self.llm_provider, "")
        return bool(key and self.llm_model)

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
