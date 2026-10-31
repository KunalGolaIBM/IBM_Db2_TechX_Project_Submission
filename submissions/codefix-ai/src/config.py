import os
from pathlib import Path
from dotenv import load_dotenv  # pyrefly: ignore[missing-import] # type: ignore

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')
load_dotenv(BASE_DIR.parent / '.env')


class Config:
    """Central Application Configuration for CodeFix AI."""

    # Flask Security & Environment
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-fallback-secret-key-codefix-ai")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("FLASK_DEBUG", "1").lower() in ("1", "true", "yes")
    PORT = int(os.getenv("PORT", 5000))

    # Ollama Local AI Runtime Configuration
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", 120))

    # IBM Db2 Database Configuration
    DB2_DATABASE = os.getenv("DB2_DATABASE", "BLUDB")
    DB2_HOSTNAME = os.getenv("DB2_HOSTNAME", "").strip()
    DB2_PORT = int(os.getenv("DB2_PORT", 32733))
    DB2_UID = os.getenv("DB2_UID", "").strip()
    DB2_PWD = os.getenv("DB2_PWD", "").strip()
    DB2_PROTOCOL = os.getenv("DB2_PROTOCOL", "TCPIP")
    DB2_SECURITY = os.getenv("DB2_SECURITY", "SSL")

    # Guardrails & Validation Limits
    MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", 10000))
    MAX_HISTORY_PER_SESSION = int(os.getenv("MAX_HISTORY_PER_SESSION", 50))

    # Supported Options
    SUPPORTED_LANGUAGES = ["python", "javascript", "java", "cpp"]
    SUPPORTED_MODES = ["write", "debug", "improve", "explain"]

    @classmethod
    def is_db2_configured(cls) -> bool:
        """Check whether valid IBM Db2 credentials have been provided."""
        return bool(cls.DB2_HOSTNAME and cls.DB2_UID and cls.DB2_PWD)

    @classmethod
    def get_db2_conn_string(cls) -> str:
        """Construct the IBM Db2 connection string for ibm_db."""
        if not cls.is_db2_configured():
            return ""
        conn_str = (
            f"DATABASE={cls.DB2_DATABASE};"
            f"HOSTNAME={cls.DB2_HOSTNAME};"
            f"PORT={cls.DB2_PORT};"
            f"PROTOCOL={cls.DB2_PROTOCOL};"
            f"UID={cls.DB2_UID};"
            f"PWD={cls.DB2_PWD};"
        )
        if cls.DB2_SECURITY:
            conn_str += f"SECURITY={cls.DB2_SECURITY};"
        return conn_str


