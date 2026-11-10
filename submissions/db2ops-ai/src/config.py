"""Validated environment based settings for Db2Ops AI."""
from functools import lru_cache
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
    return Settings()
