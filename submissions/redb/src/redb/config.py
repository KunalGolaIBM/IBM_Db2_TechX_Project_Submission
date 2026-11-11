"""Runtime configuration, read from environment (and a local .env if present)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    db2_host: str = field(default_factory=lambda: os.getenv("DB2_HOST", "localhost"))
    db2_port: int = field(default_factory=lambda: int(os.getenv("DB2_PORT", "50000")))
    db2_database: str = field(default_factory=lambda: os.getenv("DB2_DATABASE", "REDB"))
    db2_user: str = field(default_factory=lambda: os.getenv("DB2_USER", "db2inst1"))
    db2_password: str = field(default_factory=lambda: os.getenv("DB2_PASSWORD", ""))
    db2_security: str = field(default_factory=lambda: os.getenv("DB2_SECURITY", "").strip())
    target_schema: str = field(default_factory=lambda: os.getenv("TARGET_SCHEMA", "RETAIL").upper())
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", "").strip())
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.5-flash"))
    gemini_embed_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_EMBED_MODEL", "models/gemini-embedding-001"))
    embed_dim: int = field(default_factory=lambda: int(os.getenv("EMBED_DIM", "768")))

    @property
    def ssl(self) -> bool:
        return self.db2_security.upper() in ("SSL", "TRUE", "1", "YES")


def get_settings() -> Settings:
    return Settings()
