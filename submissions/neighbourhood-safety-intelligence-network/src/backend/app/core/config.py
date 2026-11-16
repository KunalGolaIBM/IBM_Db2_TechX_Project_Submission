import os
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs from a .env file without overriding real environment variables."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"").strip("'"))


_load_env_file(BASE_DIR / ".env")

DEV_JWT_SECRET = "local-development-only-jwt-secret-change-me"  # nosec B105 - dev default; refused when APP_ENV=production


def _env(*names: str, default: str = "") -> str:
    """First non-empty environment variable among ``names``."""
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


class Settings:
    PROJECT_NAME: str = "Neighbourhood Safety Intelligence Network"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    APP_ENV: str = os.getenv("APP_ENV", "development")
    # IBM Db2 is the only database. DATABASE_MODE is kept for status reporting.
    DATABASE_MODE: str = "db2"

    # IBM Db2 connection. The DB2_NAME / DB2_USERNAME / DB2_SSL spellings (used by the Db2 VS Code
    # extension setup) are accepted as aliases.
    DB2_HOST: str = os.getenv("DB2_HOST", "localhost")
    DB2_PORT: int = int(os.getenv("DB2_PORT", "50000"))
    DB2_DATABASE: str = _env("DB2_DATABASE", "DB2_NAME", default="TESTDB")
    DB2_USER: str = _env("DB2_USER", "DB2_USERNAME", default="db2inst1")
    DB2_PASSWORD: str = os.getenv("DB2_PASSWORD", "")
    DB2_SECURITY: str = "SSL" if _env("DB2_SECURITY", "DB2_SSL", default="").lower() in ("ssl", "true", "1", "yes") else ""
    DB2_SCHEMA: str = os.getenv("DB2_SCHEMA", "")  # schema of the app tables when connecting as a least-privilege user

    # JWT & Auth
    JWT_SECRET: str = os.getenv("JWT_SECRET", DEV_JWT_SECRET)
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    

    # CORS
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]

    # Local AI through Ollama (IBM Granite models); nothing leaves the machine
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_CHAT_MODEL: str = os.getenv("OLLAMA_CHAT_MODEL", "granite3.3:2b")
    OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "granite-embedding:278m")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "768"))
    ENABLE_VECTOR_SEARCH: bool = os.getenv("ENABLE_VECTOR_SEARCH", "true").lower() in ("1", "true", "yes")
    ENABLE_LLM_BRIEFING: bool = os.getenv("ENABLE_LLM_BRIEFING", "true").lower() in ("1", "true", "yes")
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "120"))

    # Login throttling (per client IP + email)
    LOGIN_MAX_ATTEMPTS: int = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
    LOGIN_WINDOW_SECONDS: int = int(os.getenv("LOGIN_WINDOW_SECONDS", "300"))


def _validate(s: "Settings") -> None:
    """Refuse to run a production deployment with development-grade secrets."""
    if s.APP_ENV.lower() == "production":
        if s.JWT_SECRET == DEV_JWT_SECRET or len(s.JWT_SECRET) < 32:
            raise RuntimeError("JWT_SECRET must be set to a random value of at least 32 characters when APP_ENV=production.")
        if "*" in s.CORS_ORIGINS:
            raise RuntimeError("CORS_ORIGINS must list explicit origins when APP_ENV=production.")


settings = Settings()
_validate(settings)
