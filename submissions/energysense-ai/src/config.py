"""Environment-backed application configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    """Settings are read when an instance is created, not at module import time."""

    db_backend: str = field(default_factory=lambda: _env("DB_BACKEND", "sqlite").lower())
    sqlite_path: str = field(default_factory=lambda: _env("SQLITE_PATH", "./energysense_demo.db"))
    db2_host: str = field(default_factory=lambda: _env("DB2_HOST", "localhost"))
    db2_port: int = field(default_factory=lambda: int(_env("DB2_PORT", "50000")))
    db2_database: str = field(default_factory=lambda: _env("DB2_DATABASE", "testdb"))
    db2_username: str = field(default_factory=lambda: _env("DB2_USERNAME", "db2inst1"))
    db2_password: str = field(default_factory=lambda: os.getenv("DB2_PASSWORD", ""))
    db2_protocol: str = field(default_factory=lambda: _env("DB2_PROTOCOL", "TCPIP").upper())
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: _env("OPENAI_MODEL", "gpt-4o-mini"))
    db2_embedding_provider: str = field(default_factory=lambda: _env("DB2_EMBEDDING_PROVIDER", "hash").lower())
    db2_embedding_model: str = field(default_factory=lambda: _env("DB2_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
    api_base_url: str = field(default_factory=lambda: _env("API_BASE_URL", "http://127.0.0.1:8000"))

    @property
    def db2_connection_string(self) -> str:
        return (
            f"DATABASE={self.db2_database};HOSTNAME={self.db2_host};"
            f"PORT={self.db2_port};PROTOCOL={self.db2_protocol};"
            f"UID={self.db2_username};PWD={self.db2_password};"
        )

    def validate(self) -> None:
        if self.db_backend not in {"sqlite", "db2"}:
            raise ValueError("DB_BACKEND must be either 'sqlite' or 'db2'.")
        if not 1 <= self.db2_port <= 65535:
            raise ValueError("DB2_PORT must be between 1 and 65535.")
        if self.db_backend == "db2":
            missing = [
                name for name, value in (
                    ("DB2_HOST", self.db2_host),
                    ("DB2_DATABASE", self.db2_database),
                    ("DB2_USERNAME", self.db2_username),
                    ("DB2_PASSWORD", self.db2_password),
                ) if not value
            ]
            if missing:
                raise ValueError("Set the following Db2 settings in .env: " + ", ".join(missing))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def sqlite_path() -> str:
    path = Path(get_settings().sqlite_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)
