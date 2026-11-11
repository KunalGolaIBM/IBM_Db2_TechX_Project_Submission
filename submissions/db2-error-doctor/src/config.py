"""Runtime configuration, read only from environment variables (.env locally)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv

_IDENTIFIER = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class ConfigError(ValueError):
    """Raised when a required setting is missing or malformed."""


def _identifier(name: str, value: str) -> str:
    """Table names cannot be bound as SQL parameters, so allow-list them."""
    value = value.strip().upper()
    if not _IDENTIFIER.match(value):
        raise ConfigError(f"{name} must be a plain Db2 identifier (A-Z, 0-9, _), got {value!r}")
    return value


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database: str
    user: str
    password: str
    security: bool
    vector_table: str
    kb_table: str
    log_table: str
    embedding_model: str
    llm_provider: str
    ollama_model: str
    ollama_base_url: str

    @property
    def dsn(self) -> str:
        parts = [
            f"DATABASE={self.database}",
            f"HOSTNAME={self.host}",
            f"PORT={self.port}",
            "PROTOCOL=TCPIP",
            f"UID={self.user}",
            f"PWD={self.password}",
        ]
        if self.security:
            parts.append("SECURITY=SSL")
        return ";".join(parts) + ";"


def load_settings() -> Settings:
    load_dotenv()
    password = os.getenv("DB2_PASSWORD", "")
    if not password or password == "your_db2_password_here":
        raise ConfigError("DB2_PASSWORD is not set. Copy .env.example to .env and fill it in.")
    for key in ("DB2_HOST", "DB2_DATABASE", "DB2_USER"):
        if ";" in os.getenv(key, "") or ";" in password:
            raise ConfigError("Db2 connection values must not contain ';'.")
    try:
        port = int(os.getenv("DB2_PORT", "50000"))
    except ValueError as exc:
        raise ConfigError("DB2_PORT must be a number.") from exc

    return Settings(
        host=os.getenv("DB2_HOST", "localhost"),
        port=port,
        database=os.getenv("DB2_DATABASE", "testdb"),
        user=os.getenv("DB2_USER", "db2inst1"),
        password=password,
        security=os.getenv("DB2_SECURITY", "false").lower() == "true",
        vector_table=_identifier("DOCTOR_VECTOR_TABLE", os.getenv("DOCTOR_VECTOR_TABLE", "DOCTOR_KB_VECTORS")),
        kb_table=_identifier("DOCTOR_KB_TABLE", os.getenv("DOCTOR_KB_TABLE", "DOCTOR_KB")),
        log_table=_identifier("DOCTOR_LOG_TABLE", os.getenv("DOCTOR_LOG_TABLE", "DOCTOR_QUERY_LOG")),
        embedding_model=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        llm_provider=os.getenv("LLM_PROVIDER", "none").lower(),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )
