"""Runtime configuration, read from environment variables and the project's .env file.

Secrets are held as SecretStr so they never appear in reprs, logs or tracebacks.
Database identifiers (schema, table names) are constants in code, never configuration,
so nothing read from the environment can reach SQL text.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
REPLAY_FILE = Path(__file__).with_name("data") / "replay.json"  # LLM_PROVIDER=replay

# "replay" answers the built-in scenarios from recorded model outputs, with no model at all (asof/replay.py).
# "watsonx" is IBM watsonx.ai through langchain-ibm (optional: pip install -r requirements-watsonx.txt).
LLMProvider = Literal["openrouter", "openai_compatible", "ollama", "watsonx", "replay"]


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.environ.get("ASOF_ENV_FILE", DEFAULT_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        validate_by_name=True,  # Settings(db2_admin_password=...) in code and tests
        validate_by_alias=True,  # DB2_USER / DB2_PASSWORD (or the older names) from the environment
    )

    # Db2 connection
    db2_host: str = "localhost"
    db2_port: int = Field(50000, ge=1, le=65535)
    db2_database: str = Field("TESTDB", pattern=r"^[A-Za-z][A-Za-z0-9_]{0,7}$")
    db2_container: str = Field("asof-db2", pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
    db2_connect_timeout_s: int = Field(15, ge=1, le=120)
    # TLS to Db2 (SECURITY=SSL in the connection string). Needed for a remote Db2 such as Db2 on Cloud. The
    # local container speaks plain TCP on 50000 unless scripts/enable_db2_tls.sh turned TLS on (port 50001).
    db2_ssl: bool = False
    # The server's certificate (or its CA's), PEM/ARM text, pinned by the driver (SSLServerCertificate).
    # Relative paths are under the project folder. Empty: the driver's own trusted authorities decide.
    db2_ssl_server_cert: str | None = Field(None, pattern=r"^[A-Za-z0-9_./~ -]{0,400}$")
    # SET CURRENT LOCK TIMEOUT for the runtime users: a ledger append waits at most this long for the
    # CHAIN_HEAD row lock instead of Db2's default of waiting forever, then fails closed.
    db2_lock_timeout_s: int = Field(10, ge=1, le=300)

    # Db2 users: owner (setup only), runtime app user, policy editor, read-only analyst.
    # DB2_USER / DB2_PASSWORD are the names the organizers' guide and AI skill use; the older
    # DB2_ADMIN_USER / DB2_ADMIN_PASSWORD are still accepted.
    db2_admin_user: str = Field("db2inst1", pattern=r"^[a-z][a-z0-9]{0,7}$",
                                validation_alias=AliasChoices("DB2_USER", "DB2_ADMIN_USER"))
    db2_admin_password: SecretStr | None = Field(None, validation_alias=AliasChoices("DB2_PASSWORD", "DB2_ADMIN_PASSWORD"))
    asof_app_user: str = Field("asofapp", pattern=r"^[a-z][a-z0-9]{0,7}$")
    asof_app_password: SecretStr | None = None
    asof_editor_user: str = Field("asofedit", pattern=r"^[a-z][a-z0-9]{0,7}$")
    asof_editor_password: SecretStr | None = None
    # Specialist decisions (inbox replies, correction notices): CONNECT, the text-reader role and EXECUTE on
    # RESOLVE_ESCALATION and DECIDE_NOTICE only, apart from the runtime user the model-facing check runs as.
    asof_review_user: str = Field("asofrev", pattern=r"^[a-z][a-z0-9]{0,7}$")
    asof_review_password: SecretStr | None = None
    # Read-only analyst ("Ask the ledger"): SELECT on the audit views only, ledger text masked.
    asof_analyst_user: str = Field("asofread", pattern=r"^[a-z][a-z0-9]{0,7}$")
    asof_analyst_password: SecretStr | None = None
    # dbt's own user (the optional analytics marts): SELECT on the four tables the marts read, and tables only in
    # its own schema, <schema>_MART. Setup creates it and generates the password.
    asof_mart_user: str = Field("asofmart", pattern=r"^[a-z][a-z0-9]{0,7}$")
    asof_mart_password: SecretStr | None = None
    # Domain-scoped users (row permissions, sql/06_domain_permissions.sql): per policy domain, an analyst for "Ask the
    # ledger" and a specialist, each of whom Db2 shows only that domain's decisions. Setup generates the passwords.
    asof_airline_analyst_user: str = Field("airread", pattern=r"^[a-z][a-z0-9]{0,7}$")
    asof_airline_analyst_password: SecretStr | None = None
    asof_airline_review_user: str = Field("airrev", pattern=r"^[a-z][a-z0-9]{0,7}$")
    asof_airline_review_password: SecretStr | None = None
    asof_bank_analyst_user: str = Field("bankread", pattern=r"^[a-z][a-z0-9]{0,7}$")
    asof_bank_analyst_password: SecretStr | None = None
    asof_bank_review_user: str = Field("bankrev", pattern=r"^[a-z][a-z0-9]{0,7}$")
    asof_bank_review_password: SecretStr | None = None
    # Policy changes over HTTP: localhost only, unless this token is set, in which case the
    # X-AsOf-Editor-Token header must match it.
    asof_editor_token: SecretStr | None = None
    # "local": the server binds to localhost; the optional shared ASOF_API_TOKEN below applies. "users": every
    # /api/ request needs a personal token from ASOF.API_USER (python -m asof.users) holding the route's role
    # (checker, auditor, editor, reviewer); the shared tokens are then not used.
    asof_auth: Literal["local", "users"] = "local"
    # Optional API token. When set, every /api/ request needs "Authorization: Bearer <token>"
    # (constant-time compare); /healthz and the static UI stay open. Unset: localhost binding only.
    asof_api_token: SecretStr | None = None
    # Chain-head anchors (asof/anchor.py): after each ledger append the new head is written, with an HMAC
    # under a key Db2 never holds, to a log outside Db2. The key lives in its own file, outside the project
    # folder and away from .env (which holds the owner's DB2_PASSWORD): setup generates it there. Default
    # $XDG_CONFIG_HOME/asof/anchor.key, else ~/.config/asof/anchor.key; mode 600; a path inside the project
    # folder is refused. No key file and no override: anchoring is off.
    asof_anchor_key_file: str | None = Field(None, pattern=r"^[A-Za-z0-9_./~ -]{0,400}$")
    # Override for containers and CI only: the key itself, from the environment. Setup never writes it.
    asof_anchor_key: SecretStr | None = None
    # Where the anchor logs go. Relative paths are under the project folder. For real use, a place the
    # database owner cannot write (another host, a write-once bucket mounted here).
    asof_anchor_dir: str = Field("var/anchors", pattern=r"^[A-Za-z0-9_./~-]{1,400}$")
    # Host headers the API answers to (comma-separated). A browser page on another site cannot reach
    # the localhost API through DNS rebinding, because its Host header is not on this list.
    asof_allowed_hosts: str = "127.0.0.1,localhost,::1"
    # A hosted public demo for judges: replay mode only, no model keys, and nothing that changes policy or sends
    # anything (see api.py). Behind its own reverse proxy on the same machine; off by default.
    asof_public_demo: bool = False
    # Live checks on the public demo (asof/demolive.py): input that is not a recorded built-in scenario is checked by
    # OpenRouter, while the built-in scenarios keep replaying. Needs ASOF_PUBLIC_DEMO=true and LLM_PROVIDER=replay, and
    # OPENROUTER_API_KEY from the process environment (a systemd EnvironmentFile), never from .env. Db2 holds the
    # daily cap for the whole demo (CLAIM_DEMO_CHECK); the per-visitor limits are kept in memory.
    asof_demo_live: bool = False
    asof_demo_live_daily_cap: int = Field(400, ge=1, le=100000)
    asof_demo_live_per_minute: int = Field(3, ge=1, le=60)
    asof_demo_live_per_day: int = Field(20, ge=1, le=1000)

    # LLM provider
    llm_provider: LLMProvider = "openrouter"
    llm_timeout_s: float = Field(60.0, gt=0, le=300)
    llm_max_retries: int = Field(2, ge=0, le=5)
    # Unset by default: several current models reject sampling parameters, and with
    # require_parameters routing an unsupported parameter means no endpoint at all.
    llm_temperature: float | None = Field(None, ge=0, le=2)
    # Every structured reply is far below this; the cap stops runaway generations.
    llm_max_output_tokens: int = Field(1000, ge=256, le=8000)
    # A hosted primary falls back to local Ollama for calls it cannot answer (recorded in the
    # ledger); "none" disables it. The local model is slower, hence its own deadline.
    llm_fallback: Literal["ollama", "none"] = "ollama"
    llm_fallback_timeout_s: float = Field(180.0, gt=0, le=600)
    # Policy intake (asof/intake.py) copies whole clauses out of a document, so its one model call gets a
    # larger output cap and a longer deadline than the calls of a check.
    asof_intake_max_output_tokens: int = Field(4000, ge=1000, le=16000)
    asof_intake_timeout_s: float = Field(150.0, gt=0, le=600)
    # Whole-check budget: no step of a check starts after it (the check then fails closed).
    asof_check_deadline_s: float = Field(300.0, gt=0, le=3600)
    # Routing (doc_id "auto", asof/router.py): Db2's vote decides clear cases; the routing agent may look at close
    # calls and confirm Db2's leader, otherwise a close call goes to a person. auto (the default): the agent runs only
    # with a model in router.MEASURED, whose run on the pinned routing test split misrouted and guessed on nothing
    # (docs/routing_eval.md); the local 7B model guessed, so with it close calls go to a person. on: any model. off: never.
    asof_router_agent: Literal["auto", "on", "off"] = "auto"

    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemini-3.1-flash-lite"

    openai_compat_base_url: str | None = None
    openai_compat_api_key: SecretStr | None = None
    openai_compat_model: str | None = None

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    # IBM watsonx.ai (LLM_PROVIDER=watsonx, and/or ASOF_INDB_PROVIDER=watsonx for Db2's own embeddings).
    # An IBM Cloud API key, the regional endpoint, and the project (or deployment space) the watsonx.ai
    # Runtime service is associated with.
    watsonx_api_key: SecretStr | None = Field(None, validation_alias=AliasChoices("WATSONX_API_KEY", "WATSONX_APIKEY"))
    watsonx_url: str = Field("https://us-south.ml.cloud.ibm.com",
                             pattern=r"^https://[a-z0-9.-]+\.(?:ml\.cloud\.ibm\.com|wxai\.ibm\.com)/?$")
    watsonx_project_id: str | None = Field(None, pattern=r"^(?:[0-9a-fA-F-]{32,36})?$")  # empty in .env = unset
    watsonx_space_id: str | None = Field(None, pattern=r"^(?:[0-9a-fA-F-]{32,36})?$")
    watsonx_model: str = Field("ibm/granite-4-h-small", pattern=r"^[A-Za-z0-9._/-]{3,120}$")
    watsonx_embedding_model: str = Field("sentence-transformers/all-minilm-l6-v2", pattern=r"^[A-Za-z0-9._/-]{3,120}$")

    # Embeddings (local, CPU): claims are embedded here, and clauses too unless Db2 does it
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # In-database embeddings (Db2 12.1.5 CREATE EXTERNAL MODEL + TO_EMBEDDING). "auto" turns them
    # on when an API key is available. The endpoint must serve the same model as embedding_model,
    # so clause vectors made in Db2 and claim vectors made here are interchangeable (setup checks).
    # IBM documents HTTPS endpoints; plain HTTP is accepted only for a local endpoint (dev use).
    asof_indb_embeddings: Literal["auto", "on", "off"] = "auto"
    embedding_api_url: str = "https://openrouter.ai/api/v1/embeddings"
    embedding_api_model: str = "sentence-transformers/all-minilm-l6-v2"
    embedding_api_key: SecretStr | None = None  # falls back to OPENROUTER_API_KEY
    # Which provider Db2's EMBEDDER model calls: "openai" (any OpenAI-compatible endpoint, above) or "watsonx"
    # (CREATE EXTERNAL MODEL ... PROVIDER WATSONX, with the watsonx settings above).
    asof_indb_provider: Literal["openai", "watsonx"] = "openai"

    @field_validator("asof_api_token", "asof_editor_token")
    @classmethod
    def _token(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and value.get_secret_value() and not re.fullmatch(r"[\x21-\x7e]{16,256}", value.get_secret_value()):
            raise ValueError("tokens must be 16 to 256 printable ASCII characters, no spaces")
        return value

    @model_validator(mode="after")
    def _public_demo(self) -> Settings:
        if self.asof_public_demo:
            if self.llm_provider != "replay":
                raise ValueError("ASOF_PUBLIC_DEMO=true runs in replay mode only: set LLM_PROVIDER=replay")
            allowed = {"openrouter_api_key"} if self.asof_demo_live else set()
            keys = [name.upper() for name in ("openrouter_api_key", "openai_compat_api_key", "watsonx_api_key",
                                              "embedding_api_key") if _is_set(getattr(self, name)) and name not in allowed]
            if keys:
                raise ValueError("ASOF_PUBLIC_DEMO=true holds no model keys" + (" but OPENROUTER_API_KEY" if allowed else "")
                                 + "; remove " + ", ".join(keys))
            if allowed and _is_set(self.openrouter_api_key) and os.environ.get("OPENROUTER_API_KEY") != \
                    self.openrouter_api_key.get_secret_value():  # type: ignore[union-attr]
                raise ValueError("ASOF_DEMO_LIVE=true takes OPENROUTER_API_KEY from the process environment only (a "
                                 "systemd EnvironmentFile), never from .env")
        elif self.asof_demo_live:
            raise ValueError("ASOF_DEMO_LIVE=true is for the public demo only: set ASOF_PUBLIC_DEMO=true, or use "
                             "LLM_PROVIDER=openrouter to check everything live")
        return self

    @model_validator(mode="after")
    def _tls(self) -> Settings:
        if self.db2_ssl_server_cert and not self.db2_ssl:
            raise ValueError("DB2_SSL_SERVER_CERT is set but DB2_SSL is not true: set DB2_SSL=true to use TLS")
        return self

    @field_validator("asof_router_agent", mode="before")
    @classmethod
    def _router_agent(cls, value: object) -> object:
        """true/false from older .env files mean on/off."""
        if isinstance(value, bool):
            return "on" if value else "off"
        if isinstance(value, str) and value.strip().lower() in {"true", "1", "yes", "false", "0", "no"}:
            return "on" if value.strip().lower() in {"true", "1", "yes"} else "off"
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("asof_anchor_key")
    @classmethod
    def _anchor_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and value.get_secret_value() and len(value.get_secret_value()) < 32:
            raise ValueError("ASOF_ANCHOR_KEY must be at least 32 characters (python -m asof.setup generates one)")
        return value

    @field_validator("openrouter_base_url", "ollama_base_url", "openai_compat_base_url", "embedding_api_url")
    @classmethod
    def _http_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("http://", "https://")):
            raise ValueError("must be an http(s) URL")
        return value

    def require(self, *names: str) -> None:
        """Fail loudly, naming the missing .env keys, before any connection is attempted."""
        missing = [ENV_NAMES.get(n, n.upper()) for n in names if not _is_set(getattr(self, n))]
        if missing:
            raise ConfigError(
                f"Missing required setting(s): {', '.join(missing)}. "
                f"Set them in {DEFAULT_ENV_FILE} (copy .env.example to start)."
            )

    def secret(self, name: str) -> str:
        """The value of a required secret setting (ConfigError naming its .env key when it is unset)."""
        self.require(name)
        value = getattr(self, name)
        return value.get_secret_value() if isinstance(value, SecretStr) else str(value)

    @property
    def db2_ssl_cert_path(self) -> Path | None:
        if not self.db2_ssl_server_cert:
            return None
        path = Path(self.db2_ssl_server_cert).expanduser()
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def db2_is_local(self) -> bool:
        return self.db2_host in ("localhost", "127.0.0.1", "::1")

    @property
    def anchor_key_path(self) -> Path:
        if self.asof_anchor_key_file:
            path = Path(self.asof_anchor_key_file).expanduser()
            return path if path.is_absolute() else Path.cwd() / path
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        return base / "asof" / "anchor.key"

    @property
    def anchor_key(self) -> bytes | None:
        """The anchor HMAC key: ASOF_ANCHOR_KEY if set, else the key file, else None (anchoring off)."""
        if _is_set(self.asof_anchor_key):
            return self.asof_anchor_key.get_secret_value().encode("utf-8")  # type: ignore[union-attr]
        path = self.anchor_key_path
        if not path.is_file():
            return None
        if path.resolve().is_relative_to(PROJECT_ROOT.resolve()):
            raise ConfigError(f"the anchor key file {path} is inside the project folder; keep it outside "
                              "(default ~/.config/asof/anchor.key) so it can never be committed")
        if path.stat().st_mode & 0o077:
            raise ConfigError(f"the anchor key file {path} is readable by other users: chmod 600 it")
        key = path.read_text(encoding="utf-8").strip().encode("utf-8")
        if len(key) < 32:
            raise ConfigError(f"the anchor key in {path} is shorter than 32 characters")
        return key

    @property
    def anchor_dir(self) -> Path:
        path = Path(self.asof_anchor_dir).expanduser()
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def embedding_key(self) -> SecretStr | None:
        if self.asof_public_demo:  # the demo's live-check key never becomes Db2's embedding key (CREATE EXTERNAL MODEL)
            return None
        return self.embedding_api_key if _is_set(self.embedding_api_key) else self.openrouter_api_key

    @property
    def indb_embeddings_wanted(self) -> bool:
        if self.asof_indb_embeddings == "off":
            return False
        if self.asof_indb_provider == "watsonx":
            return self.asof_indb_embeddings == "on" or self.watsonx_ready
        return self.asof_indb_embeddings == "on" or _is_set(self.embedding_key)

    @property
    def watsonx_ready(self) -> bool:
        return _is_set(self.watsonx_api_key) and (_is_set(self.watsonx_project_id) or _is_set(self.watsonx_space_id))

    @property
    def llm_ready(self) -> bool:
        """Whether the configured provider has what it needs to answer (a key, or an endpoint and model).
        Ollama needs no key; whether its server runs is only known on the first call."""
        if self.llm_provider == "openrouter":
            return _is_set(self.openrouter_api_key)
        if self.llm_provider == "replay":
            return REPLAY_FILE.is_file()
        if self.llm_provider == "openai_compatible":
            return (_is_set(self.openai_compat_base_url) and _is_set(self.openai_compat_model)
                    and _is_set(self.openai_compat_api_key))
        if self.llm_provider == "watsonx":
            return self.watsonx_ready
        return True

    @property
    def llm_model_name(self) -> str:
        return {
            "openrouter": self.openrouter_model,
            "openai_compatible": self.openai_compat_model or "",
            "ollama": self.ollama_model,
            "watsonx": self.watsonx_model,
            "replay": "recorded outputs",
        }[self.llm_provider]


ENV_NAMES = {"db2_admin_user": "DB2_USER", "db2_admin_password": "DB2_PASSWORD", "watsonx_api_key": "WATSONX_API_KEY"}


# Values copied from .env.example without being filled in count as missing, so a judge without a
# key gets a clear message instead of every check silently failing on a 401.
PLACEHOLDER = re.compile(r"your-(api-)?key-here|^change-me", re.I)


def _is_set(value: object) -> bool:
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    return value not in (None, "") and not (isinstance(value, str) and PLACEHOLDER.search(value))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
