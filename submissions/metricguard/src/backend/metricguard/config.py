"""Runtime configuration loaded from environment variables (and an optional .env file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db2_host: str = "localhost"
    db2_port: int = 50000
    db2_database: str = "MGDB"
    db2_user: str = "db2inst1"
    db2_password: SecretStr = SecretStr("")
    db2_schema: str = "METRICGUARD"
    # Optional least-privilege account used for analytical (read-only) queries.
    db2_reader_user: str | None = None
    db2_reader_password: SecretStr | None = None
    # Optional least-privilege account for the audit log: INSERT + SELECT on QUERY_AUDIT_LOG only.
    db2_audit_user: str | None = None
    db2_audit_password: SecretStr | None = None
    # TLS (required for IBM Cloud Db2; usually off for local Community Edition).
    db2_security: bool = False
    db2_ssl_server_certificate: str | None = None

    query_timeout_seconds: int = Field(default=15, ge=1, le=300)
    max_result_rows: int = Field(default=500, ge=1, le=10000)

    # --- AI planner (Stage 2; provider selection added in Stage 3.5) ---
    # AI_PROVIDER (preferred) selects the planner. See docs/AI_PROVIDER_CONFIGURATION.md for the precedence rules.
    #   meta       LangChain -> Meta Model API (real inference). 503 PLANNER_UNAVAILABLE if MODEL_API_KEY is missing.
    #   anthropic  LangChain -> Anthropic (optional legacy adapter). 503 without ANTHROPIC_API_KEY.
    #   demo       the labelled DEMO_RULE_BASED rule planner.
    #   auto       meta if MODEL_API_KEY is set, else anthropic if ANTHROPIC_API_KEY is set, else demo. (default)
    ai_provider: Literal["auto", "meta", "anthropic", "demo"] | None = None
    # Deprecated alias, used only when AI_PROVIDER is unset: auto | llm (any real provider, never demo) | demo.
    planner_mode: Literal["auto", "llm", "demo"] | None = None

    # Meta Model API (OpenAI-compatible Chat Completions). Key env var is MODEL_API_KEY per Meta's docs.
    model_api_key: SecretStr | None = None
    meta_model: str = "muse-spark-1.3"
    meta_base_url: str = "https://api.meta.ai/v1"
    # Optional Chat Completions `reasoning_effort` (documented at https://dev.meta.ai/docs/reasoning). `none` is not
    # offered because Muse Spark rejects it with HTTP 400. When unset, no reasoning parameter is sent and the model
    # reasons at its own level. `low` is the measured demo setting (see docs/AI_PROVIDER_CONFIGURATION.md).
    meta_reasoning_effort: Literal["minimal", "low", "medium", "high", "xhigh", "max"] | None = None

    # Anthropic (optional). PLANNER_MODEL / PLANNER_EFFORT / ANTHROPIC_BASE_URL apply to this provider only.
    anthropic_api_key: SecretStr | None = None
    planner_model: str = "claude-sonnet-5-5"
    # Optional API base URL (proxies; tests point it at a local fake provider). Default: Anthropic API.
    anthropic_base_url: str | None = None
    # Per-attempt provider timeout. The OpenAI/Anthropic SDKs retry a timed-out attempt, so the worst-case planning
    # wait is about timeout * (retries + 1) + backoff. 30 s * 2 + backoff stays below the browser's 90 s analyze
    # timeout (frontend/lib/api/client.ts), so the UI always receives the API's own answer (or its 503).
    planner_timeout_seconds: float = Field(default=30, ge=1, le=300)
    planner_max_retries: int = Field(default=1, ge=0, le=5)
    planner_effort: Literal["low", "medium", "high"] = "low"

    app_env: str = "development"
    app_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    @field_validator("meta_reasoning_effort", mode="before")
    @classmethod
    def _empty_effort_means_unset(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("anthropic_api_key", "model_api_key", mode="before")
    @classmethod
    def _ignore_placeholder_key(cls, value: object) -> object:
        # Empty values and the .env.example placeholder mean "not configured".
        if value is None or (isinstance(value, str) and (not value.strip() or value.startswith("your_"))):
            return None
        return value

    @property
    def meta_configured(self) -> bool:
        return self.model_api_key is not None

    @property
    def anthropic_configured(self) -> bool:
        return self.anthropic_api_key is not None

    @property
    def llm_configured(self) -> bool:
        """True when at least one real LLM provider has credentials."""
        return self.meta_configured or self.anthropic_configured

    @property
    def selected_provider(self) -> Literal["meta", "anthropic", "demo"] | None:
        """Which planner serves requests. None means 'none can': the API answers 503, it never falls back to demo.

        Precedence: AI_PROVIDER, else the deprecated PLANNER_MODE, else auto.
        """
        choice = self.ai_provider
        if choice is None:
            legacy = self.planner_mode or "auto"
            choice = {"auto": "auto", "demo": "demo", "llm": "llm"}[legacy]  # type: ignore[assignment]
        if choice == "demo":
            return "demo"
        if choice == "meta":
            return "meta" if self.meta_configured else None
        if choice == "anthropic":
            return "anthropic" if self.anthropic_configured else None
        # auto / legacy llm: Meta is preferred, Anthropic is the fallback *credential*, never demo for "llm"
        if self.meta_configured:
            return "meta"
        if self.anthropic_configured:
            return "anthropic"
        return "demo" if choice == "auto" else None

    @property
    def reader_configured(self) -> bool:
        return bool(self.db2_reader_user and self.db2_reader_password)

    @property
    def audit_configured(self) -> bool:
        return bool(self.db2_audit_user and self.db2_audit_password)

    def connection_string(self, *, reader: bool = False, role: Literal["admin", "reader", "audit"] | None = None) -> str:
        role = role or ("reader" if reader else "admin")
        user = self.db2_user
        password = self.db2_password.get_secret_value()
        if role == "reader" and self.reader_configured:
            user = self.db2_reader_user
            password = self.db2_reader_password.get_secret_value()  # type: ignore[union-attr]
        elif role == "audit" and self.audit_configured:
            user = self.db2_audit_user
            password = self.db2_audit_password.get_secret_value()  # type: ignore[union-attr]
        parts = [
            f"DATABASE={self.db2_database}",
            f"HOSTNAME={self.db2_host}",
            f"PORT={self.db2_port}",
            "PROTOCOL=TCPIP",
            f"UID={user}",
            f"PWD={password}",
            "CONNECTTIMEOUT=10",
        ]
        if self.db2_security:
            parts.append("SECURITY=SSL")
            if self.db2_ssl_server_certificate:
                parts.append(f"SSLServerCertificate={self.db2_ssl_server_certificate}")
        return ";".join(parts) + ";"

    def redacted_target(self) -> str:
        return f"{self.db2_user}@{self.db2_host}:{self.db2_port}/{self.db2_database}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
