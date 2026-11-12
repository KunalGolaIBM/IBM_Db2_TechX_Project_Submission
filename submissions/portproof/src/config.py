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

# A personal, never-committed overlay for API keys, loaded after ``.env`` and
# without override: anything already set in the environment or in ``.env`` wins,
# so this only fills in what those leave blank. It exists so a key can live in
# one file that no tooling reads for any other purpose.
_local_env = find_dotenv(".env.local", usecwd=True)
if _local_env:
    load_dotenv(_local_env, override=False)

#: Marks PortProof's own connections so a Db2 WLM workload can leash them.
APPL_NAME = "portproof-prover"

#: The ledger schema. Fixed, because the DDL, the SQL PL procedure names and the
#: GRANTs all spell it out; see the note in :func:`_base`.
PORTPROOF_SCHEMA = "PORTPROOF"


def schema_override_warning() -> str:
    """A warning if DB2_SCHEMA is set to something PortProof will not honour."""
    requested = os.getenv("DB2_SCHEMA", "").strip().upper()
    if requested and requested != PORTPROOF_SCHEMA:
        return (
            f"DB2_SCHEMA={requested} is ignored: the ledger schema is fixed at "
            f"{PORTPROOF_SCHEMA} by sql/01_schema.sql and sql/03_grants.sql"
        )
    return ""


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
        # Reported, not honoured, and deliberately not configurable: the schema
        # name is baked into sql/01_schema.sql, the procedure names the ledger
        # writes go through, and the GRANTs in sql/03_grants.sql. An env var
        # that silently fails to move any of that would be worse than no env
        # var, so DB2_SCHEMA is read only to warn when it disagrees.
        schema=PORTPROOF_SCHEMA,
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
class SourceDbConfig:
    """Connection details for a source engine used as ground truth."""

    host: str
    port: int
    database: str
    user: str
    password: str

    def redacted(self) -> str:
        return f"{self.user}@{self.host}:{self.port}/{self.database}"


def postgres_config() -> SourceDbConfig:
    """PostgreSQL settings. Absent configuration means the embedded DuckDB
    stand-in is used instead, with its known divergences declared."""
    return SourceDbConfig(
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", "5433")),
        database=os.getenv("PG_DATABASE", "pptest"),
        user=os.getenv("PG_USER", "postgres"),
        password=os.getenv("PG_PASSWORD", ""),
    )


@dataclass(frozen=True)
class MySqlConfig:
    """Connection details for the real MySQL used as a source-of-truth engine.

    PortProof originally emulated MySQL with DuckDB in PostgreSQL mode. That is
    sufficient for syntax but not for *semantics*: MySQL's default collation is
    case-insensitive and PostgreSQL's is not, so a statement whose whole point
    was that divergence compared equal on both engines and was certified
    equivalent when it was not. Where a real MySQL is reachable it is used; where
    it is not, the prover declines to rule rather than guess (see
    :func:`src.counterexample.prove_semantics`).
    """

    host: str
    port: int
    database: str
    user: str
    password: str

    def redacted(self) -> str:
        return f"{self.user}@{self.host}:{self.port}/{self.database}"


def mysql_config() -> MySqlConfig:
    """MySQL settings. Absent configuration is not an error -- it means the
    MySQL source engine is simply unavailable, and the caller degrades."""
    return MySqlConfig(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3307")),
        database=os.getenv("MYSQL_DATABASE", "pptest"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
    )


@dataclass(frozen=True)
class LlmConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    max_repair_attempts: int

    @property
    def is_mock(self) -> bool:
        return self.provider in ("mock", "rules", "")

    @property
    def label(self) -> str:
        """What to show a reader: the model, not the transport."""
        return "deterministic rules" if self.is_mock else self.model


#: Per-provider defaults, so supplying a key is the only required step.
#: Each entry is (base URL, model, environment variables to read the key from).
#: ``gemini`` points at Google's OpenAI-compatible surface, which means the same
#: :class:`src.llm.HttpRepairLLM` serves Gemini, Groq, watsonx and a local
#: server with no branching anywhere in the repair loop.
_PROVIDER_DEFAULTS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "gemini": (
        "https://generativelanguage.googleapis.com/v1beta/openai",
        # The dated ids (gemini-2.5-flash) are not all exposed on every key,
        # measured 2026-11-10: the floating alias is. Pin it in LLM_MODEL if you
        # want a fixed one.
        "gemini-flash-latest",
        ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    ),
    "http": (
        "https://api.groq.com/openai/v1",
        "llama-3.3-70b-versatile",
        ("GROQ_API_KEY",),
    ),
}


def llm_config() -> LlmConfig:
    """LLM settings. ``mock`` is the default so the project runs with no keys."""
    provider = os.getenv("LLM_PROVIDER", "mock").strip().lower()
    base_default, model_default, key_vars = _PROVIDER_DEFAULTS.get(
        provider, ("", "llama-3.3-70b-versatile", ())
    )
    api_key = os.getenv("LLM_API_KEY", "").strip()
    for var in key_vars:
        if api_key:
            break
        api_key = os.getenv(var, "").strip()
    return LlmConfig(
        provider=provider,
        model=os.getenv("LLM_MODEL", "").strip() or model_default,
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL", "").strip() or base_default,
        max_repair_attempts=int(os.getenv("MAX_REPAIR_ATTEMPTS", "3")),
    )


def embedding_model_name() -> str:
    return os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
