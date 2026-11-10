"""
CatalogLens Configuration Module.
Loads environment variables safely and defines system-wide settings.
"""
from functools import lru_cache
import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Find .env in project root or current working directory
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()


class Settings(BaseModel):
    # App Settings
    app_name: str = "CatalogLens"
    app_version: str = "1.0.0"
    app_description: str = "An Agentic System for Understanding Undocumented Enterprise Databases"
    debug: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # IBM Db2 Connection Settings
    db2_host: str = os.getenv("DB2_HOST", "localhost")
    db2_port: int = int(os.getenv("DB2_PORT", "50000"))
    db2_database: str = os.getenv("DB2_DATABASE", "SAMPLE")
    db2_username: str = os.getenv("DB2_USERNAME", "db2inst1")
    db2_password: str = os.getenv("DB2_PASSWORD", "")
    db2_security: str = os.getenv("DB2_SECURITY", "")
    db2_schema: str = os.getenv("DB2_SCHEMA", "ENTERPRISE")
    db2_timeout: int = int(os.getenv("DB2_TIMEOUT", "15"))

    # Anthropic Claude Settings
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-7-sonnet-20250219")
    max_tokens: int = int(os.getenv("MAX_TOKENS", "4096"))
    temperature: float = float(os.getenv("TEMPERATURE", "0.1"))

    # Server Settings
    backend_host: str = os.getenv("BACKEND_HOST", "127.0.0.1")
    backend_port: int = int(os.getenv("BACKEND_PORT", "8000"))
    backend_url: str = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
    demo_mode: bool = os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")

    def has_anthropic_key(self) -> bool:
        return bool(self.anthropic_api_key and len(self.anthropic_api_key.strip()) > 5)

    def has_db2_credentials(self) -> bool:
        return bool(self.db2_host and self.db2_database and self.db2_username and self.db2_password)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
