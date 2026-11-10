"""Configuration loaded from a private env file that lives OUTSIDE the submission folder.

DB_ENV_FILE (environment variable) names the file. Default: <repo root>/.env.drifttrace,
i.e. two directories above submissions/drifttrace/. Secrets are never printed or logged.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

SUBMISSION_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = SUBMISSION_DIR.parent.parent / ".env.drifttrace"


def load_env() -> Path | None:
    path = Path(os.environ.get("DB_ENV_FILE", str(DEFAULT_ENV_FILE))).expanduser()
    if path.is_file():
        load_dotenv(path, override=False)
        return path
    return None


@dataclass(frozen=True)
class Settings:
    database: str
    hostname: str
    port: str
    uid: str
    pwd: str
    security: str
    ai_model: str
    google_api_key: str
    schema: str = ""
    admin_uid: str = ""
    admin_pwd: str = ""

    def dsn(self, admin: bool = False) -> str:
        uid, pwd = (self.admin_uid or self.uid, self.admin_pwd or self.pwd) if admin else (self.uid, self.pwd)
        parts = [
            f"DATABASE={self.database}",
            f"HOSTNAME={self.hostname}",
            f"PORT={self.port}",
            "PROTOCOL=TCPIP",
            f"UID={uid}",
            f"PWD={pwd}",
        ]
        if self.schema:
            parts.append(f"CURRENTSCHEMA={self.schema}")
        if self.security:
            parts.append(f"SECURITY={self.security}")
        return ";".join(parts) + ";"

    def __repr__(self) -> str:  # never leak credentials through repr
        return f"Settings(database={self.database!r}, hostname={self.hostname!r}, port={self.port!r}, uid={self.uid!r}, ai_model={self.ai_model!r})"


def get_settings() -> Settings:
    load_env()
    return Settings(
        database=os.environ.get("DB2_DATABASE", ""),
        hostname=os.environ.get("DB2_HOSTNAME", ""),
        port=os.environ.get("DB2_PORT", "50000"),
        uid=os.environ.get("DB2_UID", ""),
        pwd=os.environ.get("DB2_PWD", ""),
        security=os.environ.get("DB2_SECURITY", "").strip(),
        ai_model=os.environ.get("AI_MODEL", "gemini-3.5-flash-lite"),
        google_api_key=os.environ.get("GOOGLE_API_KEY", ""),
        schema=os.environ.get("DB2_SCHEMA", "").strip().upper(),
        admin_uid=os.environ.get("DB2_ADMIN_UID", ""),
        admin_pwd=os.environ.get("DB2_ADMIN_PWD", ""),
    )
