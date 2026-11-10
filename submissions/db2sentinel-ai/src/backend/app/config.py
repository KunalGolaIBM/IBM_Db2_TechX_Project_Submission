import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Project Info
    PROJECT_NAME: str = "Db2Sentinel AI"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"

    # IBM Db2 Connection Parameters
    DB2_HOST: str = os.getenv("DB2_HOST", "localhost")
    DB2_PORT: int = int(os.getenv("DB2_PORT", "50000"))
    DB2_DATABASE: str = os.getenv("DB2_DATABASE", "SENTINELDB")
    DB2_USERNAME: str = os.getenv("DB2_USERNAME", "sentinel_user")
    DB2_PASSWORD: str = os.getenv("DB2_PASSWORD", "password")
    DB2_SECURITY: str = os.getenv("DB2_SECURITY", "NONE")  # 'SSL' or 'NONE'
    DB2_SSL_CERTIFICATE: str = os.getenv("DB2_SSL_CERTIFICATE", "")
    DB2_DEMO_FALLBACK: bool = os.getenv("DB2_DEMO_FALLBACK", "true").lower() in ("true", "1", "yes")

    # AI / LLM Configuration
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock")  # 'gemini', 'openai', 'ollama', 'mock'
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-1.5-flash")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Backend Server
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "127.0.0.1")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173")

    # Detection Engine Thresholds
    BRUTE_FORCE_THRESHOLD: int = 5
    BRUTE_FORCE_WINDOW_MINUTES: int = 15
    PASSWORD_SPRAY_ACCOUNT_THRESHOLD: int = 3
    VOLUME_ANOMALY_ZSCORE_THRESHOLD: float = 3.0

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

settings = Settings()
