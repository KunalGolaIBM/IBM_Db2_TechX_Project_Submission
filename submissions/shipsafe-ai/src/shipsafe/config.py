"""Configuration management for ShipSafe AI.

All settings come from environment variables (optionally loaded from a local
`.env` file). Credentials are never hardcoded.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv() -> None:
    """Load KEY=VALUE pairs from ./.env without overriding real env vars."""
    env_file = Path.cwd() / ".env"
    if not env_file.is_file():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


@dataclass
class Db2Config:
    """IBM Db2 connection settings."""
    host: str = "localhost"
    port: int = 50000
    database: str = "SAMPLE"
    username: str = "db2inst1"
    password: str = ""
    security: str = "NONE"
    schema: str = "SHIPSAFE"

    @classmethod
    def from_env(cls) -> "Db2Config":
        return cls(
            host=os.getenv("DB2_HOST", "localhost"),
            port=int(os.getenv("DB2_PORT", "50000")),
            database=os.getenv("DB2_DATABASE", "SAMPLE"),
            username=os.getenv("DB2_USERNAME", "db2inst1"),
            password=os.getenv("DB2_PASSWORD", ""),
            security=os.getenv("DB2_SECURITY", "NONE").upper(),
            schema=os.getenv("DB2_SCHEMA", "SHIPSAFE").upper(),
        )

    def connection_string(self) -> str:
        conn = (
            f"DATABASE={self.database};HOSTNAME={self.host};PORT={self.port};"
            f"PROTOCOL=TCPIP;UID={self.username};PWD={self.password};"
        )
        if self.security == "SSL":
            conn += "SECURITY=SSL;"
        return conn


@dataclass
class ShipSafeConfig:
    """Master configuration for ShipSafe AI."""
    env: str = "development"
    # "db2" (default) or "sqlite" (offline unit tests only).
    backend: str = "db2"
    db2: Db2Config = field(default_factory=Db2Config.from_env)
    enable_mcp: bool = True
    # "hashing" (offline, default) or "huggingface" (sentence-transformers).
    embedding_provider: str = "hashing"
    embedding_dimension: int = 384
    policies_dir: str = str(Path(__file__).resolve().parents[2] / "policies")

    @classmethod
    def load(cls) -> "ShipSafeConfig":
        return cls(
            env=os.getenv("SHIPSAFE_ENV", "development"),
            backend=os.getenv("SHIPSAFE_DB_BACKEND", "db2").lower(),
            db2=Db2Config.from_env(),
            enable_mcp=os.getenv("SHIPSAFE_ENABLE_MCP", "true").lower() in ("1", "true", "yes"),
            embedding_provider=os.getenv("SHIPSAFE_EMBEDDINGS", "hashing").lower(),
            embedding_dimension=int(os.getenv("SHIPSAFE_VECTOR_DIMENSION", "384")),
            policies_dir=os.getenv("SHIPSAFE_POLICIES_DIR", cls.policies_dir),
        )
