"""
MediTwin AI — Configuration Settings
Loads environment variables and provides typed settings.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent


class Db2Settings(BaseSettings):
    """IBM Db2 connection settings."""
    host: str = Field(default="localhost", alias="DB2_HOST")
    port: int = Field(default=50000, alias="DB2_PORT")
    database: str = Field(default="MEDITWIN", alias="DB2_DATABASE")
    user: str = Field(default="db2inst1", alias="DB2_USER")
    password: str = Field(default="", alias="DB2_PASSWORD")
    schema_name: str = Field(default="MEDITWIN", alias="DB2_SCHEMA")

    @property
    def connection_string(self) -> str:
        return (
            f"DATABASE={self.database};"
            f"HOSTNAME={self.host};"
            f"PORT={self.port};"
            f"PROTOCOL=TCPIP;"
            f"UID={self.user};"
            f"PWD={self.password};"
        )

    model_config = {"env_prefix": "", "populate_by_name": True}


class GeminiSettings(BaseSettings):
    """Gemini API settings."""
    api_key: str = Field(default="", alias="GEMINI_API_KEY")
    model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")

    model_config = {"env_prefix": "", "populate_by_name": True}


class AppSettings(BaseSettings):
    """Application settings."""
    name: str = Field(default="MediTwin AI", alias="APP_NAME")
    env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="APP_DEBUG")
    max_upload_size_mb: int = Field(default=10, alias="MAX_UPLOAD_SIZE_MB")

    model_config = {"env_prefix": "", "populate_by_name": True}


# Singleton instances
db2_settings = Db2Settings()
gemini_settings = GeminiSettings()
app_settings = AppSettings()

# Disclaimer text
DISCLAIMER = (
    "MediTwin AI is a demonstration prototype for organizing and explaining "
    "synthetic medical records. It is not a medical device and does not provide "
    "diagnosis or treatment advice."
)

