"""Runtime configuration, read from environment variables and the project's .env file.

Secrets are held as SecretStr so they never appear in reprs, logs or tracebacks.
Database identifiers (schema, table names) are constants in code, never configuration,
so nothing read from the environment can reach SQL text.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
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
        validate_by_name=True,  # Settings(db2_admin_password=...) in code and tests
        validate_by_alias=True,  # DB2_USER / DB2_PASSWORD (or the older names) from the environment
    )

    # Db2 connection
    db2_host: str = "localhost"
    db2_port: int = Field(50000, ge=1, le=65535)
    db2_database: str = Field("TESTDB", pattern=r"^[A-Za-z][A-Za-z0-9_]{0,7}$")
    db2_container: str = Field("asof-db2", pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
    db2_connect_timeout_s: int = Field(15, ge=1, le=120)

    # Db2 users: owner (setup only), runtime app user, policy editor, read-only analyst.
    # DB2_USER / DB2_PASSWORD are the names the organizers' guide and AI skill use; the older
    # DB2_ADMIN_USER / DB2_ADMIN_PASSWORD are still accepted.
    db2_admin_user: str = Field("db2inst1", pattern=r"^[a-z][a-z0-9]{0,7}$",
                                validation_alias=AliasChoices("DB2_USER", "DB2_ADMIN_USER"))
    db2_admin_password: SecretStr | None = Field(None, validation_alias=AliasChoices("DB2_PASSWORD", "DB2_ADMIN_PASSWORD"))
    asof_app_user: str = Field("asofapp", pattern=r"^[a-z][a-z0-9]{0,7}$")
    asof_app_password: SecretStr | None = None
    asof_editor_user: str = Field("asofedit", pattern=r"^[a-z][a-z0-9]{0,7}$")
    asof_editor_password: SecretStr | None = None
    # Read-only analyst ("Ask the ledger"): SELECT on the audit views only, ledger text masked.
    asof_analyst_user: str = Field("asofread", pattern=r"^[a-z][a-z0-9]{0,7}$")
    asof_analyst_password: SecretStr | None = None
    # Policy changes over HTTP: localhost only, unless this token is set, in which case the
    # X-AsOf-Editor-Token header must match it.
    asof_editor_token: SecretStr | None = None
    # Optional API token. When set, every /api/ request needs "Authorization: Bearer <token>"
    # (constant-time compare); /healthz and the static UI stay open. Unset: localhost binding only.
    asof_api_token: SecretStr | None = None
    # Host headers the API answers to (comma-separated). A browser page on another site cannot reach
    # the localhost API through DNS rebinding, because its Host header is not on this list.
    asof_allowed_hosts: str = "127.0.0.1,localhost,::1"

    # LLM provider
    llm_provider: LLMProvider = "openrouter"
    llm_timeout_s: float = Field(60.0, gt=0, le=300)
    llm_max_retries: int = Field(2, ge=0, le=5)
    # Unset by default: several current models reject sampling parameters, and with
    # require_parameters routing an unsupported parameter means no endpoint at all.
    llm_temperature: float | None = Field(None, ge=0, le=2)
    # Every structured reply is far below this; the cap stops runaway generations.
    llm_max_output_tokens: int = Field(1000, ge=256, le=8000)
    # A hosted primary falls back to local Ollama for calls it cannot answer (recorded in the
    # ledger); "none" disables it. The local model is slower, hence its own deadline.
    llm_fallback: Literal["ollama", "none"] = "ollama"
    llm_fallback_timeout_s: float = Field(180.0, gt=0, le=600)

    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemini-3.1-flash-lite"

    openai_compat_base_url: str | None = None
    openai_compat_api_key: SecretStr | None = None
    openai_compat_model: str | None = None

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    # Embeddings (local, CPU): claims are embedded here, and clauses too unless Db2 does it
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # In-database embeddings (Db2 12.1.5 CREATE EXTERNAL MODEL + TO_EMBEDDING). "auto" turns them
    # on when an API key is available. The endpoint must serve the same model as embedding_model,
    # so clause vectors made in Db2 and claim vectors made here are interchangeable (setup checks).
    # IBM documents HTTPS endpoints; plain HTTP is accepted only for a local endpoint (dev use).
    asof_indb_embeddings: Literal["auto", "on", "off"] = "auto"
    embedding_api_url: str = "https://openrouter.ai/api/v1/embeddings"
    embedding_api_model: str = "sentence-transformers/all-minilm-l6-v2"
    embedding_api_key: SecretStr | None = None  # falls back to OPENROUTER_API_KEY

    @field_validator("asof_api_token", "asof_editor_token")
    @classmethod
    def _token(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and value.get_secret_value() and not re.fullmatch(r"[\x21-\x7e]{16,256}", value.get_secret_value()):
            raise ValueError("tokens must be 16 to 256 printable ASCII characters, no spaces")
        return value

    @field_validator("openrouter_base_url", "ollama_base_url", "openai_compat_base_url", "embedding_api_url")
    @classmethod
    def _http_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("http://", "https://")):
            raise ValueError("must be an http(s) URL")
        return value

    def require(self, *names: str) -> None:
        """Fail loudly, naming the missing .env keys, before any connection is attempted."""
        missing = [ENV_NAMES.get(n, n.upper()) for n in names if not _is_set(getattr(self, n))]
        if missing:
            raise ConfigError(
                f"Missing required setting(s): {', '.join(missing)}. "
                f"Set them in {DEFAULT_ENV_FILE} (copy .env.example to start)."
            )

    @property
    def embedding_key(self) -> SecretStr | None:
        return self.embedding_api_key if _is_set(self.embedding_api_key) else self.openrouter_api_key

    @property
    def indb_embeddings_wanted(self) -> bool:
        if self.asof_indb_embeddings == "off":
            return False
        return self.asof_indb_embeddings == "on" or _is_set(self.embedding_key)

    @property
    def llm_model_name(self) -> str:
        return {
            "openrouter": self.openrouter_model,
            "openai_compatible": self.openai_compat_model or "",
            "ollama": self.ollama_model,
        }[self.llm_provider]


ENV_NAMES = {"db2_admin_user": "DB2_USER", "db2_admin_password": "DB2_PASSWORD"}


# Values copied from .env.example without being filled in count as missing, so a judge without a
# key gets a clear message instead of every check silently failing on a 401.
PLACEHOLDER = re.compile(r"your-key-here|^change-me", re.I)


def _is_set(value: object) -> bool:
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    return value not in (None, "") and not (isinstance(value, str) and PLACEHOLDER.search(value))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
