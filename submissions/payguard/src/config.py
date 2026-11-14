"""Validated settings. Environment variables override the private .env file."""
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8", extra="ignore", frozen=True,
    )
    db2_host: str = "localhost"
    db2_port: str = "50000"
    db2_database: str = "PAYGUARD"
    db2_user: str = "db2inst1"
    db2_password: str = Field("", repr=False)
    db2_ssl: bool = False
    db2_pool_min: int = Field(2, ge=0)
    db2_pool_max: int = Field(10, ge=1, le=100)
    db2_pool_timeout: float = Field(5, gt=0)
    db2_connect_timeout: int = Field(5, ge=1)
    db2_query_timeout: int = Field(3, ge=1)
    embed_dim: int = Field(768, ge=1, le=32768)
    embed_provider: Literal["local", "gemini", "auto"] = "local"
    gemini_api_key: str = Field("", repr=False)
    gemini_model: str = "gemini-3.8-flash"
    gemini_embed_model: str = "gemini-embedding-001"
    gemini_timeout: float = Field(5, gt=0)
    investigation_timeout: float = Field(10, gt=0)
    paypal_client_id: str = ""
    paypal_client_secret: str = Field("", repr=False)
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    paypal_currency: str = "USD"
    review_threshold: int = Field(35, ge=0, le=100)
    block_threshold: int = Field(65, ge=0, le=100)
    cache_size: int = Field(512, ge=0)
    entity_cache_ttl: float = Field(5, ge=0)
    pattern_cache_ttl: float = Field(10, ge=0)
    embedding_cache_ttl: float = Field(60, ge=0)
    rate_limit_per_minute: int = Field(60, ge=1)
    rate_limit_max_ips: int = Field(10000, ge=1)
    platform_api_key: str = Field("", repr=False)
    platform_demo_enabled: bool = True

    @model_validator(mode="after")
    def validate_limits(self):
        if self.db2_pool_min > self.db2_pool_max:
            raise ValueError("DB2_POOL_MIN must be <= DB2_POOL_MAX")
        if self.review_threshold >= self.block_threshold:
            raise ValueError("REVIEW_THRESHOLD must be below BLOCK_THRESHOLD")
        return self

    @property
    def llm_enabled(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def paypal_enabled(self) -> bool:
        return bool(self.paypal_client_id and self.paypal_client_secret)

    @property
    def db2_conn_str(self) -> str:
        value = (f"DATABASE={self.db2_database};HOSTNAME={self.db2_host};PORT={self.db2_port};"
                 f"PROTOCOL=TCPIP;UID={self.db2_user};PWD={self.db2_password};"
                 f"CONNECTTIMEOUT={self.db2_connect_timeout};"
                 f"QUERYTIMEOUT={self.db2_query_timeout};")
        return value + ("SECURITY=SSL;" if self.db2_ssl else "")


settings = Settings()
