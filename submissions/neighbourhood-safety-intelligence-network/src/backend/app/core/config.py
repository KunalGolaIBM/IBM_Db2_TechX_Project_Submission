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
    
    # JWT & Auth
    JWT_SECRET: str = os.getenv("JWT_SECRET", "super_secret_civic_safety_network_jwt_key_change_in_production")
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

settings = Settings()
