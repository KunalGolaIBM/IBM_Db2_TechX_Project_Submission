"""Application settings — environment-driven configuration.

Design rules (M1):
- Every value is overridable via environment variable (pydantic-settings).
- Secrets are ``SecretStr`` and never serialized into API responses.
- Safe defaults make the app start with ZERO external services (mock adapters).
- Placeholders only in committed examples — never real credentials.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvironmentName = Literal["development", "testing", "production"]
AdapterMode = Literal["mock", "real"]
InjectionMode = Literal["off", "flag", "block"]
VectorStrategy = Literal["cosine", "dot", "euclidean"]


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """Effective runtime configuration (env vars > .env file > defaults)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    # --- Application -------------------------------------------------------
    app_name: str = "Db2 Ops Copilot"
    app_version: str = "0.1.0"
    environment: EnvironmentName = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    # Comma-separated in env; list in Python.
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    serve_frontend: bool = True
    log_level: str = "INFO"
    log_file: str = ""

    # --- Adapter selection -------------------------------------------------
    # "mock" (default) = fully offline development/testing.
    # "real"          = Db2 + Ollama + LangChain integrations (requires
    #                   requirements-integration.txt and running services).
    adapter_mode: AdapterMode = "mock"

    # --- IBM Db2 (target of the real database adapter) ---------------------
    # Names match the root .env.example. Never put real values in git.
    db2_host: str = Field(default="127.0.0.1", validation_alias="DB2_HOST")
    db2_port: int = Field(default=50000, validation_alias="DB2_PORT", ge=1, le=65535)
    db2_dbname: str = Field(default="testdb", validation_alias="DB2_DBNAME")
    db2_ro_user: str = Field(default="db2ro", validation_alias="DB2_RO_USER")
    db2_ro_password: SecretStr = Field(
        default=SecretStr(""), validation_alias="DB2_RO_PASSWORD"
    )
    db2_connect_timeout_ms: int = 3000
    # Schema that owns the application tables (APP_AUDIT, DEMO_*, COPILOT_KB).
    # Introspection reads SYSCAT for THIS schema — not the login user's schema.
    db2_app_schema: str = Field(default="APP", validation_alias="DB2_APP_SCHEMA")
    # Schema holding the EXPLAIN_* tables (SYSTOOLS when created with
    # SYSPROC.SYSINSTALLOBJECTS('EXPLAIN','C',NULL,NULL)). Interpolated into
    # fixed SQL templates, so it is validated as a plain identifier.
    db2_explain_schema: str = Field(
        default="SYSTOOLS", validation_alias="DB2_EXPLAIN_SCHEMA"
    )
    # Default / maximum rows returned by the DBA monitoring tools.
    dba_default_limit: int = Field(default=20, ge=1, le=100)

    # --- Agent (M3) --------------------------------------------------------
    # auto = LangGraph when installed, else the built-in runner (same nodes,
    # same routing); langgraph / builtin force one engine.
    agent_engine: Literal["auto", "langgraph", "builtin"] = "auto"
    agent_max_tool_calls: int = Field(default=8, ge=1, le=16)
    agent_stale_stats_days: int = Field(default=30, ge=1, le=3650)
    # Optional LLM-written narrative on top of the deterministic report.
    agent_use_llm: bool = False
    # Human-approval policy for maintenance actions.
    approval_ttl_seconds: int = Field(default=900, ge=1, le=86400)
    # Executing an APPROVED action against a real Db2 needs a separate,
    # privileged account and an explicit opt-in. Off by default: approvals are
    # still recorded and audited, nothing is executed.
    agent_actions_enabled: bool = False
    db2_admin_user: str = Field(default="", validation_alias="DB2_ADMIN_USER")
    db2_admin_password: SecretStr = Field(
        default=SecretStr(""), validation_alias="DB2_ADMIN_PASSWORD"
    )

    # --- Ollama models -----------------------------------------------------
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434", validation_alias="OLLAMA_BASE_URL"
    )
    ollama_llm_model: str = Field(
        default="granite4.2:3b", validation_alias="OLLAMA_LLM_MODEL"
    )
    ollama_embed_model: str = Field(
        default="nomic-embed-text:v1.5", validation_alias="OLLAMA_EMBED_MODEL"
    )
    ollama_timeout_ms: int = 30000
    embedding_dimensions: int = 768  # nomic-embed-text:v1.5
    # Bounded retry for transient failures (connection resets, 5xx) — M2.3.
    ollama_max_retries: int = Field(default=2, ge=0, le=5)
    ollama_retry_backoff_ms: int = Field(default=250, ge=0, le=5000)

    # --- Db2 vector store (langchain-db2 DB2VS) ----------------------------
    # Table managed by DB2VS; created by migration 004 with the exact DDL the
    # package itself would run (so the read-only account needs no CREATE).
    vector_table_name: str = Field(
        default="COPILOT_KB", validation_alias="VECTOR_TABLE_NAME"
    )
    # Db2 distance metric used by VECTOR_DISTANCE ranking.
    vector_distance_strategy: VectorStrategy = Field(
        default="cosine", validation_alias="VECTOR_DISTANCE_STRATEGY"
    )

    # --- SQL security policy (see docs/ARCHITECTURE.md §Security) ----------
    sql_max_length: int = 5000
    sql_max_ast_nodes: int = 500
    sql_max_subqueries: int = 6
    sql_max_joins: int = 8
    sql_max_in_list: int = 200
    sql_max_rows: int = 100
    sql_query_timeout_ms: int = 10000
    sql_enforce_row_limit: bool = True
    # Best-effort EXPLAIN dry-run before executing generated SQL (M2.6).
    # Disabled automatically at runtime when the account lacks EXPLAIN rights.
    sql_explain_dry_run: bool = True
    # Comma-separated schemas the generated-SQL guard must never touch.
    sql_denied_schemas: str = (
        "SYSCAT,SYSIBM,SYSSTAT,SYSPROC,SYSIBMADM,SYSIBMSECURITY,SYSTOOLS"
    )

    # --- Security / prompt-injection ---------------------------------------
    injection_mode: InjectionMode = "block"
    security_max_message_length: int = 4000

    # --- Non-secret view of DB state for the dashboard ----------------------
    # (host/port/name are not credentials; passwords are NEVER exposed.)

    @field_validator(
        "cors_origins", "sql_denied_schemas", mode="before"
    )
    @classmethod
    def _coerce_csv(cls, value: object) -> object:
        if isinstance(value, (list, tuple)):
            return ",".join(str(v) for v in value)
        return value

    @field_validator("db2_app_schema", "db2_explain_schema")
    @classmethod
    def _plain_identifier(cls, value: str) -> str:
        cleaned = value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$#@]{0,127}", cleaned):
            raise ValueError("must be a plain SQL identifier")
        return cleaned

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        level = value.upper()
        if level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError(f"invalid log level: {value}")
        return level

    # Derived properties ---------------------------------------------------
    @property
    def cors_origins_list(self) -> list[str]:
        return _split_csv(self.cors_origins)

    @property
    def denied_schemas_list(self) -> list[str]:
        return [s.upper() for s in _split_csv(self.sql_denied_schemas)]

    @property
    def app_schema(self) -> str:
        """Uppercased application schema name (Db2 stores unquoted identifiers
        upper-cased; SYSCAT comparisons are case-sensitive)."""
        return self.db2_app_schema.strip().upper() or "APP"

    @property
    def explain_schema(self) -> str:
        return self.db2_explain_schema.strip().upper() or "SYSTOOLS"

    @property
    def qualified_app_table(self) -> str:
        return f"{self.app_schema}.{self.vector_table_name.upper()}"

    @property
    def is_mock(self) -> bool:
        return self.adapter_mode == "mock"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor (dependency-injection friendly)."""
    return Settings()


def reset_settings_cache() -> None:
    """Clear the cache — used by tests after mutating the environment."""
    get_settings.cache_clear()
