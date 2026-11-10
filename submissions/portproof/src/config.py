"""Configuration, read from the environment only.

Nothing secret is ever hard-coded or committed: copy ``.env.example`` to ``.env``
(which is git-ignored) and fill it in. ``find_dotenv`` searches upwards, so the
file may sit next to the code or at the repository root.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True), override=False)

#: Marks PortProof's own connections so a Db2 WLM workload can leash them.
APPL_NAME = "portproof-prover"


class ConfigError(RuntimeError):
    """Raised when required configuration is absent."""


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(
            f"Missing required environment variable {name!r}. "
            "Copy .env.example to .env and fill it in."
        )
    return value


@dataclass(frozen=True)
class Db2Config:
    """Connection details for one Db2 identity."""

    host: str
    port: int
    database: str
    user: str
    password: str
    schema: str

    def dsn(self) -> str:
        """Build the CLI connection string.

        ``DeferredPrepare=0`` is essential, not cosmetic. With the Db2 CLI
        default, ``PREPARE`` is held back on the client until execution, so
        ``ibm_db.prepare()`` reports success for SQL the server would reject --
        measured on CE 12.1.5. PortProof's whole verdict rests on PREPARE being
        a real server-side compile, so deferred prepare is switched off.
        """
        return (
            f"DATABASE={self.database};HOSTNAME={self.host};PORT={self.port};"
            f"PROTOCOL=TCPIP;UID={self.user};PWD={self.password};"
            "DeferredPrepare=0;"
        )

    def redacted(self) -> str:
        return f"{self.user}@{self.host}:{self.port}/{self.database} (schema {self.schema})"


def _base(user_var: str, pwd_var: str) -> Db2Config:
    return Db2Config(
        host=os.getenv("DB2_HOST", "localhost"),
        port=int(os.getenv("DB2_PORT", "50000")),
        database=os.getenv("DB2_DATABASE", "testdb"),
        user=_require(user_var),
        password=_require(pwd_var),
        schema=os.getenv("DB2_SCHEMA", "PORTPROOF").upper(),
    )


def runtime_config() -> Db2Config:
    """The least-privilege identity the application runs as."""
    return _base("DB2_USER", "DB2_PASSWORD")


def setup_config() -> Db2Config:
    """The schema owner, used only by setup and by adversarial-fixture creation.

    Falls back to the runtime identity so a judge can run everything with a
    single account if they prefer.
    """
    if os.getenv("DB2_SETUP_USER", "").strip():
        return _base("DB2_SETUP_USER", "DB2_SETUP_PASSWORD")
    return runtime_config()


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    max_repair_attempts: int

    @property
    def is_mock(self) -> bool:
        return self.provider == "mock"


def llm_config() -> LlmConfig:
    """LLM settings. ``mock`` is the default so the project runs with no keys."""
    provider = os.getenv("LLM_PROVIDER", "mock").strip().lower()
    return LlmConfig(
        provider=provider,
        model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=os.getenv("LLM_BASE_URL", ""),
        max_repair_attempts=int(os.getenv("MAX_REPAIR_ATTEMPTS", "3")),
    )


def embedding_model_name() -> str:
    return os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
