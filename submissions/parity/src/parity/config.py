"""Runtime settings loaded from environment variables.

No secret has a default value. If a value is missing, the
field stays empty and the executor fails with a clear error
instead of guessing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseSettings:
    """Connection settings for one database."""

    host: str = ""
    port: int = 0
    user: str = ""
    password: str = ""
    database: str = ""

    def require_complete(self, label: str) -> None:
        """Raise ValueError when any field is empty."""
        missing = [
            name
            for name, value in (
                ("host", self.host),
                ("user", self.user),
                ("password", self.password),
                ("database", self.database),
            )
            if not value
        ]
        if self.port == 0:
            missing.append("port")
        if missing:
            raise ValueError(f"{label} settings missing: {', '.join(missing)}")


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    if raw == "":
        return default
    return int(raw)


def load_settings() -> tuple[DatabaseSettings, DatabaseSettings]:
    """Load source and Db2 settings from the environment."""
    source = DatabaseSettings(
        host=os.environ.get("PARITY_SOURCE_HOST", "localhost"),
        port=_int_env("PARITY_SOURCE_PORT", 5432),
        user=os.environ.get("PARITY_SOURCE_USER", ""),
        password=os.environ.get("PARITY_SOURCE_PASSWORD", ""),
        database=os.environ.get("PARITY_SOURCE_DB", ""),
    )
    db2 = DatabaseSettings(
        host=os.environ.get("PARITY_DB2_HOST", "localhost"),
        port=_int_env("PARITY_DB2_PORT", 50000),
        user=os.environ.get("PARITY_DB2_USER", ""),
        password=os.environ.get("PARITY_DB2_PASSWORD", ""),
        database=os.environ.get("PARITY_DB2_DB", ""),
    )
    return source, db2


@dataclass(frozen=True)
class LlmSettings:
    """Settings for one model provider."""

    model: str = "recorded-model"
    base_url: str = "http://localhost"
    api_key: str = ""

    def validate(self) -> None:
        """Raise ValueError when the settings are not usable."""
        if not self.model.strip():
            raise ValueError("PARITY_LLM_MODEL must not be empty")
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("PARITY_LLM_BASE_URL must start with http:// or https://")

    @property
    def is_replay_only(self) -> bool:
        """True when no key is set, so only cached calls can run."""
        return not self.api_key

    def require_live(self) -> None:
        """Raise ValueError when a live call has no API key."""
        self.validate()
        if self.is_replay_only:
            raise ValueError(
                "LLM API key is required for live calls. "
                "Set PARITY_LLM_API_KEY or use replay mode."
            )


def load_llm_settings() -> LlmSettings:
    """Load LLM settings from the environment."""
    settings = LlmSettings(
        model=os.environ.get("PARITY_LLM_MODEL", "recorded-model"),
        base_url=os.environ.get("PARITY_LLM_BASE_URL", "http://localhost"),
        api_key=os.environ.get("PARITY_LLM_API_KEY", ""),
    )
    settings.validate()
    return settings
