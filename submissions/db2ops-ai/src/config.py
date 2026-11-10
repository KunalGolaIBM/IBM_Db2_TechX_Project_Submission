"""Validated environment based settings for Db2Ops AI."""
from functools import lru_cache
import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db2_database: str = "DB2OPS"
    db2_hostname: str = "localhost"
    db2_port: int = Field(default=50000, ge=1, le=65535)
    db2_protocol: str = "TCPIP"
    db2_uid: str = "db2inst1"
    db2_pwd: str = ""
    db2_security: str = ""
    db2_schema: str = "DB2INST1"
    db2_max_rows: int = Field(default=500, ge=1, le=5000)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    def connection_string(self) -> str:
        parts = [
            f"DATABASE={self.db2_database}", f"HOSTNAME={self.db2_hostname}",
            f"PORT={self.db2_port}", f"PROTOCOL={self.db2_protocol}",
            f"UID={self.db2_uid}", f"PWD={self.db2_pwd}",
        ]
        if self.db2_security:
            parts.append(f"SECURITY={self.db2_security}")
        return ";".join(parts) + ";"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Streamlit Community Cloud stores secrets in st.secrets, not in the
    # process environment. Copy only the known app settings into env vars
    # before Pydantic reads them; never log or display their values.
    try:
        import streamlit as st

        for key in (
            "DB2_DATABASE", "DB2_HOSTNAME", "DB2_PORT", "DB2_PROTOCOL",
            "DB2_UID", "DB2_PWD", "DB2_SECURITY", "DB2_SCHEMA",
            "DB2_MAX_ROWS", "OPENAI_API_KEY", "OPENAI_MODEL",
        ):
            if key in st.secrets and key not in os.environ:
                os.environ[key] = str(st.secrets[key])
    except Exception:
        # No Streamlit secrets file is normal in local development.
        pass
    return Settings()
