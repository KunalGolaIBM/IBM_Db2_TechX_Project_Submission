"""Configuration is read once from the environment (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
SQL_DIR = BASE_DIR / "sql"
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "src" / "api" / "static"

load_dotenv(BASE_DIR / ".env")


def _str(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _int(name: str, default: int) -> int:
    try:
        return int(_str(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(_str(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    embedding_model: str
    embedding_dim: int

    llm_provider: str
    llm_base_url: str
    llm_model: str
    llm_api_key: str
    llm_temperature: float
    llm_timeout: int

    retriever_top_k: int
    prompt_version: str = "1.0.0"

    @property
    def llm_is_mock(self) -> bool:
        """Mock mode is a first-class mode, not an error path.

        It keeps the whole application runnable, testable and demoable with
        zero API keys - which is what a reviewer cloning the repo needs.
        """
        return self.llm_provider.lower() == "mock" or not self.llm_api_key

    @property
    def db_conn_string(self) -> str:
        return (
            f"DATABASE={self.db_name};HOSTNAME={self.db_host};PORT={self.db_port};"
            f"PROTOCOL=TCPIP;UID={self.db_user};PWD={self.db_password};"
            "ConnectTimeout=30;"
        )


settings = Settings(
    db_host=_str("DB_HOST", "localhost"),
    db_port=_int("DB_PORT", 50000),
    db_name=_str("DB_NAME", "YOJANADB"),
    db_user=_str("DB_USER", "db2inst1"),
    db_password=_str("DB_PASSWORD", "change-me-locally"),
    embedding_model=_str("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
    embedding_dim=_int("EMBEDDING_DIM", 384),
    llm_provider=_str("LLM_PROVIDER", "openai_compatible"),
    llm_base_url=_str("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/"),
    llm_model=_str("LLM_MODEL", "llama-3.3-70b-versatile"),
    llm_api_key=_str("LLM_API_KEY", ""),
    llm_temperature=_float("LLM_TEMPERATURE", 0.1),
    llm_timeout=_int("LLM_TIMEOUT_SECONDS", 45),
    retriever_top_k=_int("RETRIEVER_TOP_K", 8),
)
