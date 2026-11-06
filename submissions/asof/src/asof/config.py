"""Runtime configuration, read from environment variables and the project's .env file.

Secrets are held as SecretStr so they never appear in reprs, logs or tracebacks.
Database identifiers (schema, table names) are constants in code, never configuration,
so nothing read from the environment can reach SQL text.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"

LLMProvider = Literal["openrouter", "openai_compatible", "ollama"]


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.environ.get("ASOF_ENV_FILE", DEFAULT_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # Db2 connection
    db2_host: str = "localhost"
    db2_port: int = Field(50000, ge=1, le=65535)
    db2_database: str = Field("TESTDB", pattern=r"^[A-Za-z][A-Za-z0-9_]{0,7}$")
    db2_container: str = Field("asof-db2", pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
    db2_connect_timeout_s: int = Field(15, ge=1, le=120)

    # Db2 users: owner (setup only), runtime app user, policy editor
    db2_admin_user: str = Field("db2inst1", pattern=r"^[a-z][a-z0-9]{0,7}$")
    db2_admin_password: SecretStr | None = None
    asof_app_user: str = Field("asofapp", pattern=r"^[a-z][a-z0-9]{0,7}$")
    asof_app_password: SecretStr | None = None
    asof_editor_user: str = Field("asofedit", pattern=r"^[a-z][a-z0-9]{0,7}$")
    asof_editor_password: SecretStr | None = None

    # LLM provider
    llm_provider: LLMProvider = "openrouter"
    llm_timeout_s: float = Field(60.0, gt=0, le=300)
    llm_max_retries: int = Field(2, ge=0, le=5)
    # Unset by default: several current models reject sampling parameters, and with
    # require_parameters routing an unsupported parameter means no endpoint at all.
    llm_temperature: float | None = Field(None, ge=0, le=2)
    # Every structured reply is far below this; the cap stops runaway generations.
    llm_max_output_tokens: int = Field(1500, ge=256, le=8000)

    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemini-3.1-flash-lite"

    openai_compat_base_url: str | None = None
    openai_compat_api_key: SecretStr | None = None
    openai_compat_model: str | None = None

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    # Embeddings (local, CPU)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    @field_validator("openrouter_base_url", "ollama_base_url", "openai_compat_base_url")
    @classmethod
    def _http_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("http://", "https://")):
            raise ValueError("must be an http(s) URL")
        return value

    def require(self, *names: str) -> None:
        """Fail loudly, naming the missing .env keys, before any connection is attempted."""
        missing = [n.upper() for n in names if not _is_set(getattr(self, n))]
        if missing:
            raise ConfigError(
                f"Missing required setting(s): {', '.join(missing)}. "
                f"Set them in {DEFAULT_ENV_FILE} (copy .env.example to start)."
            )

    @property
    def llm_model_name(self) -> str:
        return {
            "openrouter": self.openrouter_model,
            "openai_compatible": self.openai_compat_model or "",
            "ollama": self.ollama_model,
        }[self.llm_provider]


def _is_set(value: object) -> bool:
    if isinstance(value, SecretStr):
        return bool(value.get_secret_value())
    return value not in (None, "")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
