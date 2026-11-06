"""
Configuration module for Db2 Sentinel AI.
Handles database credentials, LLM providers, and agent behavioral parameters.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "src" / "data"
DOCS_DIR = BASE_DIR / "docs"

# Load .env if present
load_dotenv(BASE_DIR / ".env")

# Db2 Connection Parameters
DB2_MODE = os.getenv("DB2_MODE", "auto").lower()  # 'live', 'emulated', or 'auto'
DB2_DATABASE = os.getenv("DB2_DATABASE", "testdb")
DB2_HOSTNAME = os.getenv("DB2_HOSTNAME", "localhost")
DB2_PORT = int(os.getenv("DB2_PORT", "50000"))
DB2_PROTOCOL = os.getenv("DB2_PROTOCOL", "TCPIP")
DB2_UID = os.getenv("DB2_UID", "db2inst1")
DB2_PWD = os.getenv("DB2_PWD", "YourSecurePassword123!")
DB2_SCHEMA = os.getenv("DB2_SCHEMA", "SENTINEL")

# LLM & AI Settings
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
WATSONX_APIKEY = os.getenv("WATSONX_APIKEY", "")
WATSONX_PROJECT_ID = os.getenv("WATSONX_PROJECT_ID", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "granite3.3:8b")

# Embedding Configuration
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "ibm-granite/granite-embedding-311m-multilingual-r2"
)

# Detection & Risk Parameters
AML_ALERT_THRESHOLD = int(os.getenv("AML_ALERT_THRESHOLD", "65"))
HIGH_RISK_THRESHOLD = int(os.getenv("HIGH_RISK_THRESHOLD", "85"))
STRUCTURING_WINDOW_HOURS = int(os.getenv("STRUCTURING_WINDOW_HOURS", "24"))
RAPID_VELOCITY_TX_COUNT = int(os.getenv("RAPID_VELOCITY_TX_COUNT", "3"))


def get_db2_conn_string() -> str:
    """Returns the native ibm_db connection string."""
    return (
        f"DATABASE={DB2_DATABASE};"
        f"HOSTNAME={DB2_HOSTNAME};"
        f"PORT={DB2_PORT};"
        f"PROTOCOL={DB2_PROTOCOL};"
        f"UID={DB2_UID};"
        f"PWD={DB2_PWD};"
    )


def get_sqlalchemy_uri() -> str:
    """Returns the SQLAlchemy URI for IBM Db2."""
    return f"db2+ibm_db://{DB2_UID}:{DB2_PWD}@{DB2_HOSTNAME}:{DB2_PORT}/{DB2_DATABASE}"
