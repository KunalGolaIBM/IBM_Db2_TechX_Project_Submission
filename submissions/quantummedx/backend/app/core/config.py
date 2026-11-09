"""Environment-based configuration. No secrets are hardcoded or defaulted."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env automatically (works the same on Windows, macOS and Linux). Real environment variables win.
_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / "backend" / ".env")


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Db2Settings:
    host: str
    port: int
    database: str
    user: str
    password: str
    pool_size: int

    @property
    def conn_str(self) -> str:
        return (
            f"DATABASE={self.database};HOSTNAME={self.host};PORT={self.port};"
            f"PROTOCOL=TCPIP;UID={self.user};PWD={self.password};"
        )


def load_db2_settings() -> Db2Settings:
    password = os.getenv("DB2_PASSWORD")
    if not password:
        raise ConfigError("DB2_PASSWORD is not set. Copy .env.example to .env and fill it in.")
    return Db2Settings(
        host=os.getenv("DB2_HOST", "localhost"),
        port=int(os.getenv("DB2_PORT", "50000")),
        database=os.getenv("DB2_DATABASE", "QMEDX"),
        user=os.getenv("DB2_USER", "db2inst1"),
        password=password,
        pool_size=int(os.getenv("DB2_POOL_SIZE", "5")),
    )
