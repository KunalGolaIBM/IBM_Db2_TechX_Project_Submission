from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .errors import DatabaseUnavailableError


SCHEMA_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def load_environment() -> None:
    # Keep credentials out of shell history; explicit process variables take precedence.
    load_dotenv(ENV_FILE, override=False, interpolate=False)


def validate_schema(value: str) -> str:
    if not SCHEMA_PATTERN.fullmatch(value):
        raise ValueError("DB2_SCHEMA must be a valid unquoted Db2 identifier")
    return value.upper()


@dataclass(frozen=True)
class Db2Config:
    dsn: str = field(repr=False)
    user: str = field(repr=False)
    password: str = field(repr=False)
    schema: str

    def require_dsn(self) -> None:
        if not self.dsn:
            raise DatabaseUnavailableError("Db2 is not configured")


@dataclass(frozen=True)
class Settings:
    db2: Db2Config
    cors_origins: tuple[str, ...]
    coach_provider: str
    coach_model: str
    ollama_base_url: str
    openai_api_key: str = field(repr=False)

    @classmethod
    def from_env(cls) -> "Settings":
        load_environment()
        origins = tuple(
            origin.strip()
            for origin in os.getenv("API_CORS_ORIGINS", "http://localhost:5173").split(",")
            if origin.strip()
        )
        provider = os.getenv("COACH_PROVIDER", "disabled").strip().lower()
        if provider not in {"disabled", "ollama", "openai"}:
            raise ValueError("COACH_PROVIDER must be disabled, ollama, or openai")
        default_model = "llama3.2" if provider == "ollama" else "gpt-4o-mini"
        return cls(
            db2=Db2Config(
                dsn=os.getenv("DB2_DSN", "").strip(),
                user=os.getenv("DB2_USER", "").strip(),
                password=os.getenv("DB2_PASSWORD", ""),
                schema=validate_schema(os.getenv("DB2_SCHEMA", "CHESS").strip()),
            ),
            cors_origins=origins,
            coach_provider=provider,
            coach_model=os.getenv("COACH_MODEL", default_model).strip(),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip(),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        )

