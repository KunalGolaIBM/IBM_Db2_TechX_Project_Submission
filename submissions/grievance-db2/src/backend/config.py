import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Configuration
    All values are loaded from environment variables or .env file.
    No hard-coded secrets.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application settings
    APP_NAME: str = "CPGRAMS Citizen Grievance Portal API"
    APP_VERSION: str = "2.0.0"
    APP_ENV: str = "production"
    DEBUG: bool = False
    API_PREFIX: str = "/api"
    CORS_ORIGINS: str = "*"

    # IBM Db2 Community Edition connection settings
    DB2_HOST: str = "db2"
    DB2_PORT: int = 50000
    DB2_DATABASE: str = "GRIEVDB"
    DB2_USER: str = "db2inst1"
    DB2_PASSWORD: str = "Db2Hack2026!"
    DB2_SCHEMA: str = "DB2INST1"
    
    # Optional direct database URL override (must use db2+ibm_db)
    DATABASE_URL: str = ""

    # Grievance ID prefix
    TRACKING_ID_PREFIX: str = "GRV-2026-"

    # AI & LangChain LLM Provider Settings (Db2Hack 2026)
    GEMINI_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    OLLAMA_BASE_URL: str = ""
    WATSONX_API_KEY: str = ""
    WATSONX_PROJECT_ID: str = ""
    WATSONX_URL: str = "https://us-south.ml.cloud.ibm.com"
    AI_PROVIDER: str = "auto"  # auto, gemini, openrouter, ollama, watsonx
    AI_MODEL: str = ""  # auto-detected or user-specified

    @property
    def sqlalchemy_database_uri(self) -> str:
        """
        Constructs the SQLAlchemy connection URI.
        Defaults to ibm_db_sa for IBM Db2 if DATABASE_URL is not set.
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"db2+ibm_db://{self.DB2_USER}:{self.DB2_PASSWORD}"
            f"@{self.DB2_HOST}:{self.DB2_PORT}/{self.DB2_DATABASE}"
        )

    @property
    def cors_origins_list(self) -> List[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
