"""
Configuration management using environment variables.
"""
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Db2 connection
    db2_host: str = "localhost"
    db2_port: int = 50000
    db2_db: str = "clinic"
    db2_user: str = "db2inst1"
    db2_password: str
    db2_schema: str = "DB2INST1"
    
    # Classification thresholds
    pii_value_threshold: float = 0.30
    pii_name_threshold: float = 0.35
    
    # Request management
    default_request_deadline_days: int = 30
    
    # API settings
    api_secret_key: str = "change-this-in-production"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    
    # LLM configuration (optional)
    llm_provider: str = "local"
    llm_model: Optional[str] = None
    
    # Mock mode — skip real Db2 (set DB_MOCK=1 for demo/dev without Docker)
    db_mock: int = 0
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # tolerate extra env vars like DB_MOCK


# Global settings instance
settings = Settings()


def get_dsn() -> str:
    """
    Build a Db2 connection string (DSN).
    
    Returns:
        str: Db2 DSN string for use with ibm_db
    """
    return (
        f"DATABASE={settings.db2_db};"
        f"HOSTNAME={settings.db2_host};"
        f"PORT={settings.db2_port};"
        f"PROTOCOL=TCPIP;"
        f"UID={settings.db2_user};"
        f"PWD={settings.db2_password};"
    )
