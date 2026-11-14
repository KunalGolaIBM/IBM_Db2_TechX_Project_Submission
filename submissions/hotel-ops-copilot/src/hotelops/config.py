"""Runtime configuration, read from environment variables (and an optional .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

SCHEMA = "HOTELOPS"


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else value


@dataclass(frozen=True)
class Db2Settings:
    host: str
    port: int
    database: str
    admin_user: str
    admin_password: str
    agent_user: str
    agent_password: str
    security: bool
    secadm_user: str = "hotelsec"
    secadm_password: str = ""

    def conn_str(self, user: str, password: str) -> str:
        parts = [
            f"DATABASE={self.database}",
            f"HOSTNAME={self.host}",
            f"PORT={self.port}",
            "PROTOCOL=TCPIP",
            f"UID={user}",
            f"PWD={password}",
            f"CURRENTSCHEMA={SCHEMA}",
        ]
        if self.security:
            parts.append("SECURITY=SSL")
        return ";".join(parts) + ";"


@dataclass(frozen=True)
class LlmSettings:
    provider: str
    model: str
    temperature: float
    rpm: float = 0.0  # client-side requests-per-minute cap (0 = no cap)

    def missing_credentials(self) -> str | None:
        """Return a human-readable reason if the selected provider has no API key, else None."""
        needed = {"gemini": ("GOOGLE_API_KEY", "GEMINI_API_KEY"), "openai": ("OPENAI_API_KEY",),
                  "watsonx": ("WATSONX_APIKEY",)}.get(self.provider, ())
        if not needed:
            return None
        for name in needed:
            value = (os.getenv(name) or "").strip()
            if value and not value.startswith(("your_", "change_me")):
                return None
        return f"LLM_PROVIDER={self.provider} needs {needed[0]} in .env"


@dataclass(frozen=True)
class Settings:
    db2: Db2Settings
    llm: LlmSettings
    embedding_model: str
    embedding_dim: int
    sql_row_limit: int


def load_settings() -> Settings:
    db2 = Db2Settings(
        host=_env("DB2_HOST", "localhost"),
        port=int(_env("DB2_PORT", "50000")),
        database=_env("DB2_DATABASE", "HOTELDB"),
        admin_user=_env("DB2_USER", "db2inst1"),
        admin_password=_env("DB2_PASSWORD", ""),
        agent_user=_env("DB2_AGENT_USER", "opsagent"),
        agent_password=_env("DB2_AGENT_PASSWORD", ""),
        security=_env("DB2_SECURITY", "false").lower() == "true",
        secadm_user=_env("DB2_SECADM_USER", "hotelsec"),
        secadm_password=_env("DB2_SECADM_PASSWORD", ""),
    )
    llm = LlmSettings(
        provider=_env("LLM_PROVIDER", "gemini").lower(),
        model=_env("LLM_MODEL", "gemini-3.5-flash"),
        temperature=float(_env("LLM_TEMPERATURE", "0")),
        # Gemini's free tier allows ~10 requests/minute; stay under it by default.
        rpm=float(_env("LLM_RPM", "8" if _env("LLM_PROVIDER", "gemini").lower() == "gemini" else "0")),
    )
    return Settings(
        db2=db2,
        llm=llm,
        embedding_model=_env("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
        embedding_dim=384,
        sql_row_limit=int(_env("SQL_ROW_LIMIT", "200")),
    )
