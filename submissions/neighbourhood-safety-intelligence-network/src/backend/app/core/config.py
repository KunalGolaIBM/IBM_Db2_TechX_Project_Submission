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

DEV_JWT_SECRET = "local-development-only-jwt-secret-change-me"


class Settings:
    PROJECT_NAME: str = "Neighbourhood Safety Intelligence Network"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Environment & Database mode
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DATABASE_MODE: str = os.getenv("DATABASE_MODE", "sqlite").lower()
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/neighbourhood_safety.db")
    
    # PostgreSQL parameters
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "neighbourhood_safety")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    
    # IBM Db2 parameters
    DB2_HOST: str = os.getenv("DB2_HOST", "")
    DB2_PORT: int = int(os.getenv("DB2_PORT", "50000"))
    DB2_DATABASE: str = os.getenv("DB2_DATABASE", "")
    DB2_USER: str = os.getenv("DB2_USER", "")
    DB2_PASSWORD: str = os.getenv("DB2_PASSWORD", "")
    DB2_SECURITY: str = os.getenv("DB2_SECURITY", "")
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

    # Semantic search with Db2 VECTOR columns (used only when DATABASE_MODE=db2)
    ENABLE_VECTOR_SEARCH: bool = os.getenv("ENABLE_VECTOR_SEARCH", "true").lower() in ("1", "true", "yes")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "384"))
    EMBEDDING_CACHE_DIR: str = os.getenv("EMBEDDING_CACHE_DIR", "")

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
