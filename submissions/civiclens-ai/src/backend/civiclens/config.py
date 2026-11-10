"""Runtime configuration loaded from environment variables (and an optional .env file).

No credential has a usable default: DB2_PASSWORD must be provided by the environment.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# submissions/civiclens-ai/.env (gitignored); process env vars take precedence.
# CIVICLENS_ENV_FILE may point elsewhere (the official validator rejects a .env inside the folder).
_ENV_FILE = Path(os.environ.get("CIVICLENS_ENV_FILE") or Path(__file__).resolve().parents[3] / ".env")
_IDENTIFIER = re.compile(r"^[A-Z][A-Z0-9_]{0,29}$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- IBM Db2 -------------------------------------------------------------
    db2_host: str = "localhost"
    db2_port: int = Field(default=50000, ge=1, le=65535)
    db2_database: str = "CIVICDB"
    db2_user: str = "db2inst1"
    db2_password: SecretStr | None = None
    db2_schema: str = "CIVICLENS"
    # "false"/"" = plain TCP (local Docker); "SSL" = TLS (Db2 on Cloud, port 50001).
    db2_security: str = "false"
    db2_ssl_server_certificate: str | None = None
    db2_connect_timeout: int = Field(default=10, ge=1, le=120)

    # --- Application -----------------------------------------------------------
    app_env: Literal["development", "test", "production"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: str = "http://localhost:5173"

    # --- AI (Phase 01+) ---------------------------------------------------------
    llm_provider: Literal["none", "openai", "anthropic", "watsonx"] = "none"
    llm_model: str | None = None  # required when llm_provider != "none"; never hardcoded
    llm_timeout_s: int = Field(default=30, ge=1, le=300)  # per model request
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    watsonx_apikey: SecretStr | None = None
    watsonx_project_id: str | None = None
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"

    # --- Agent limits ---------------------------------------------------------------
    agent_max_steps: int = Field(default=6, ge=1, le=12)  # model/tool iterations
    agent_timeout_s: int = Field(default=90, ge=5, le=600)  # whole-run wall clock

    # --- Authentication --------------------------------------------------------------
    # "id:role:token" entries, comma separated. role is "analyst" or "reviewer".
    # Unset => every investigation endpoint fails closed with 503.
    civiclens_auth_tokens: SecretStr | None = None

    @field_validator("cors_origins")
    @classmethod
    def _validate_cors(cls, value: str) -> str:
        """Only explicit scheme://host[:port] origins; a wildcard would defeat the point of CORS."""
        for origin in (o.strip() for o in value.split(",") if o.strip()):
            if "*" in origin:
                raise ValueError("CORS_ORIGINS must list explicit origins; wildcards are not allowed.")
            if not re.fullmatch(r"https?://[A-Za-z0-9.-]+(:\d{1,5})?", origin):
                raise ValueError(f"Invalid CORS origin {origin!r}: expected scheme://host[:port] (no path).")
        return value

    @field_validator("db2_schema")
    @classmethod
    def _validate_schema(cls, value: str) -> str:
        value = value.strip().upper()
        if not _IDENTIFIER.match(value):
            raise ValueError("DB2_SCHEMA must be an unquoted Db2 identifier (A-Z, 0-9, _).")
        return value

    @property
    def db2_ssl_enabled(self) -> bool:
        return self.db2_security.strip().upper() in {"SSL", "TRUE", "1", "YES"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def db2_connection_string(self) -> str:
        """Build an ibm_db connection string. Raises if no password is configured."""
        if self.db2_password is None or not self.db2_password.get_secret_value():
            raise RuntimeError("DB2_PASSWORD is not set; refusing to connect.")
        for name, value in {
            "DB2_HOST": self.db2_host,
            "DB2_DATABASE": self.db2_database,
            "DB2_USER": self.db2_user,
        }.items():
            if ";" in value or "=" in value:
                raise ValueError(f"{name} contains an illegal character.")
        parts = [
            f"DATABASE={self.db2_database}",
            f"HOSTNAME={self.db2_host}",
            f"PORT={self.db2_port}",
            "PROTOCOL=TCPIP",
            f"UID={self.db2_user}",
            f"PWD={self.db2_password.get_secret_value()}",
            f"CONNECTTIMEOUT={self.db2_connect_timeout}",
        ]
        if self.db2_ssl_enabled:
            parts.append("SECURITY=SSL")
            if self.db2_ssl_server_certificate:
                parts.append(f"SSLServerCertificate={self.db2_ssl_server_certificate}")
        return ";".join(parts) + ";"

    def redacted_target(self) -> str:
        """Human-readable connection target that never includes the password."""
        tls = "ssl" if self.db2_ssl_enabled else "tcp"
        return f"db2://{self.db2_user}@{self.db2_host}:{self.db2_port}/{self.db2_database} ({tls})"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
