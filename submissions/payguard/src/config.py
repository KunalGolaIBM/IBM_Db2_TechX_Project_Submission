"""Central configuration, read from environment variables (.env supported)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # dotenv is optional
    pass


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # --- IBM Db2 ---
    db2_host: str = field(default_factory=lambda: os.getenv("DB2_HOST", "localhost"))
    db2_port: str = field(default_factory=lambda: os.getenv("DB2_PORT", "50000"))
    db2_database: str = field(default_factory=lambda: os.getenv("DB2_DATABASE", "PAYGUARD"))
    db2_user: str = field(default_factory=lambda: os.getenv("DB2_USER", "db2inst1"))
    db2_password: str = field(default_factory=lambda: os.getenv("DB2_PASSWORD", ""))
    db2_ssl: bool = field(default_factory=lambda: _bool("DB2_SSL", False))

    # --- Embeddings / LLM ---
    embed_dim: int = field(default_factory=lambda: int(os.getenv("EMBED_DIM", "768")))
    embed_provider: str = field(default_factory=lambda: os.getenv("EMBED_PROVIDER", "local"))  # local|gemini|auto
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    gemini_embed_model: str = field(default_factory=lambda: os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001"))

    # --- PayPal (sandbox) ---
    paypal_client_id: str = field(default_factory=lambda: os.getenv("PAYPAL_CLIENT_ID", ""))
    paypal_client_secret: str = field(default_factory=lambda: os.getenv("PAYPAL_CLIENT_SECRET", ""))
    paypal_base_url: str = field(default_factory=lambda: os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com"))
    paypal_currency: str = field(default_factory=lambda: os.getenv("PAYPAL_CURRENCY", "USD"))

    # --- Risk thresholds ---
    review_threshold: int = field(default_factory=lambda: int(os.getenv("REVIEW_THRESHOLD", "35")))
    block_threshold: int = field(default_factory=lambda: int(os.getenv("BLOCK_THRESHOLD", "65")))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def paypal_enabled(self) -> bool:
        return bool(self.paypal_client_id and self.paypal_client_secret)

    @property
    def db2_conn_str(self) -> str:
        s = (
            f"DATABASE={self.db2_database};HOSTNAME={self.db2_host};PORT={self.db2_port};"
            f"PROTOCOL=TCPIP;UID={self.db2_user};PWD={self.db2_password};"
        )
        if self.db2_ssl:
            s += "SECURITY=SSL;"
        return s


settings = Settings()
