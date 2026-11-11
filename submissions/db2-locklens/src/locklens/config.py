"""Configuration loaded from environment variables (optionally a local ``.env`` file).

Secrets are never given defaults, never included in ``repr()`` and never rendered by the UI.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Mapping

from .errors import ConfigError
from .models import Severity

_HOST_RE = re.compile(r"^[A-Za-z0-9._:\-]{1,255}$")
_DB_RE = re.compile(r"^[A-Za-z0-9_#@$]{1,128}$")
_USER_RE = re.compile(r"^[A-Za-z0-9_.@#$\-]{1,128}$")
_SCHEMA_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,29}$")
_TRUE = {"1", "true", "yes", "on", "ssl"}
_FALSE = {"", "0", "false", "no", "off"}


def load_env_file(path: str | os.PathLike[str] = ".env") -> bool:
    """Load KEY=VALUE pairs from ``path`` without overriding real environment variables."""
    p = Path(path)
    if not p.is_file():
        return False
    try:
        from dotenv import load_dotenv  # optional convenience

        load_dotenv(p, override=False)
        return True
    except ImportError:
        pass
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return True


@dataclass(frozen=True)
class Settings:
    db_host: str = "localhost"
    db_port: int = 50000
    db_name: str = "testdb"
    db_user: str = "db2inst1"
    db_password: str = field(default="", repr=False)
    db_ssl: bool = False
    connect_timeout: int = 15
    schema: str = "LOCKLENS"
    poll_seconds: int = 5
    auto_refresh: bool = False
    wait_warn_seconds: int = 10
    wait_critical_seconds: int = 60
    max_rows: int = 2000
    auto_record: bool = True
    record_min_severity: Severity = Severity.WARNING
    llm_enabled: bool = False
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    llm_timeout: int = 60
    log_level: str = "INFO"

    @property
    def has_password(self) -> bool:
        return bool(self.db_password)

    def fingerprint(self) -> str:
        """Non-secret identity of the target database (safe to use as a cache key)."""
        return f"{self.db_user}@{self.db_host}:{self.db_port}/{self.db_name}"

    def redacted(self) -> dict[str, object]:
        return {
            "db_host": self.db_host, "db_port": self.db_port, "db_name": self.db_name,
            "db_user": self.db_user, "db_password": "set" if self.has_password else "NOT SET",
            "db_ssl": self.db_ssl, "schema": self.schema, "poll_seconds": self.poll_seconds,
            "wait_warn_seconds": self.wait_warn_seconds,
            "wait_critical_seconds": self.wait_critical_seconds,
            "llm_enabled": self.llm_enabled, "ollama_url": self.ollama_url,
            "ollama_model": self.ollama_model,
        }

    def with_runtime_overrides(self, **changes: object) -> "Settings":
        """Return a copy with UI-adjustable, non-secret values changed (validated)."""
        new = replace(self, **changes)  # type: ignore[arg-type]
        problems = _validate_numbers(new)
        if problems:
            raise ConfigError(problems)
        return new

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None, *,
                 require_password: bool = True) -> "Settings":
        env = os.environ if environ is None else environ
        problems: list[str] = []

        def get(name: str, default: str) -> str:
            return str(env.get(name, default)).strip()

        def get_int(name: str, default: int) -> int:
            raw = get(name, str(default))
            try:
                return int(raw)
            except ValueError:
                problems.append(f"{name} must be an integer (got {raw!r}).")
                return default

        def get_bool(name: str, default: bool) -> bool:
            raw = get(name, "true" if default else "false").lower()
            if raw in _TRUE:
                return True
            if raw in _FALSE:
                return False
            problems.append(f"{name} must be true or false (got {raw!r}).")
            return default

        sev_raw = get("LOCKLENS_RECORD_MIN_SEVERITY", "WARNING")
        try:
            min_sev = Severity.parse(sev_raw)
        except ValueError:
            problems.append("LOCKLENS_RECORD_MIN_SEVERITY must be INFO, WARNING or CRITICAL.")
            min_sev = Severity.WARNING

        password = str(env.get("DB2_PASSWORD", ""))
        settings = cls(
            db_host=get("DB2_HOST", "localhost"),
            db_port=get_int("DB2_PORT", 50000),
            db_name=get("DB2_DATABASE", "testdb"),
            db_user=get("DB2_USER", "db2inst1"),
            db_password=password,
            db_ssl=get_bool("DB2_SECURITY", False),
            connect_timeout=get_int("LOCKLENS_CONNECT_TIMEOUT", 15),
            schema=get("LOCKLENS_SCHEMA", "LOCKLENS").upper(),
            poll_seconds=get_int("LOCKLENS_POLL_SECONDS", 5),
            auto_refresh=get_bool("LOCKLENS_AUTO_REFRESH", False),
            wait_warn_seconds=get_int("LOCKLENS_WAIT_WARN_SECONDS", 10),
            wait_critical_seconds=get_int("LOCKLENS_WAIT_CRITICAL_SECONDS", 60),
            max_rows=get_int("LOCKLENS_MAX_ROWS", 2000),
            auto_record=get_bool("LOCKLENS_AUTO_RECORD", True),
            record_min_severity=min_sev,
            llm_enabled=get_bool("LOCKLENS_LLM_ENABLED", False),
            ollama_url=get("LOCKLENS_OLLAMA_URL", "http://localhost:11434"),
            ollama_model=get("LOCKLENS_OLLAMA_MODEL", "llama3.2:3b"),
            llm_timeout=get_int("LOCKLENS_LLM_TIMEOUT", 60),
            log_level=get("LOCKLENS_LOG_LEVEL", "INFO").upper(),
        )
        problems.extend(_validate_text(settings))
        problems.extend(_validate_numbers(settings))
        if require_password and not password:
            problems.append("DB2_PASSWORD is not set. Copy .env.example to .env and set it.")
        if problems:
            raise ConfigError(problems)
        return settings


def _validate_text(s: Settings) -> list[str]:
    out: list[str] = []
    if not _HOST_RE.match(s.db_host):
        out.append("DB2_HOST contains characters that are not allowed in a host name.")
    if not _DB_RE.match(s.db_name):
        out.append("DB2_DATABASE contains characters that are not allowed.")
    if not _USER_RE.match(s.db_user):
        out.append("DB2_USER contains characters that are not allowed.")
    if not _SCHEMA_RE.match(s.schema):
        out.append("LOCKLENS_SCHEMA must start with a letter and contain only letters, "
                   "digits and underscores (max 30 characters).")
    if any(c in s.db_password for c in ("\x00", "\n", "\r")):
        out.append("DB2_PASSWORD contains control characters.")
    if not re.match(r"^https?://[A-Za-z0-9._:\-]+(:\d+)?/?$", s.ollama_url):
        out.append("LOCKLENS_OLLAMA_URL must look like http://host:port.")
    return out


def _validate_numbers(s: Settings) -> list[str]:
    out: list[str] = []
    if not 1 <= s.db_port <= 65535:
        out.append("DB2_PORT must be between 1 and 65535.")
    if not 2 <= s.poll_seconds <= 300:
        out.append("LOCKLENS_POLL_SECONDS must be between 2 and 300.")
    if not 1 <= s.wait_warn_seconds <= 86400:
        out.append("LOCKLENS_WAIT_WARN_SECONDS must be between 1 and 86400.")
    if s.wait_critical_seconds <= s.wait_warn_seconds:
        out.append("LOCKLENS_WAIT_CRITICAL_SECONDS must be greater than the warning threshold.")
    if not 1 <= s.connect_timeout <= 300:
        out.append("LOCKLENS_CONNECT_TIMEOUT must be between 1 and 300.")
    if not 10 <= s.max_rows <= 100000:
        out.append("LOCKLENS_MAX_ROWS must be between 10 and 100000.")
    if not 1 <= s.llm_timeout <= 600:
        out.append("LOCKLENS_LLM_TIMEOUT must be between 1 and 600.")
    return out
