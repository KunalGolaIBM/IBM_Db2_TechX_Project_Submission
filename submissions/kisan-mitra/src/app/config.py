import os
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv

# Base project paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"
DB_DIR = BASE_DIR / "db"

# Load environment variables
load_dotenv(BASE_DIR / ".env")

class AppConfig:
    """Central configuration for Kisan Mitra AI Assistant."""
    
    # IBM Db2 Database Configuration
    DB2_HOST: str = os.getenv("DB2_HOST", "localhost")
    DB2_PORT: int = int(os.getenv("DB2_PORT", "50000"))
    DB2_DATABASE: str = os.getenv("DB2_DATABASE", "KISANMIT")
    DB2_USER: str = os.getenv("DB2_USER", "db2inst1")
    DB2_PASSWORD: str = os.getenv("DB2_PASSWORD", "KisanMitra2026!")
    DB2_READONLY_USER: str = os.getenv("DB2_READONLY_USER", "kisan_ro")
    DB2_READONLY_PASSWORD: str = os.getenv("DB2_READONLY_PASSWORD", "KisanReadOnly2026!")
    DB2_DRIVER: str = os.getenv("DB2_DRIVER", "{IBM DB2 ODBC DRIVER}")
    DB2_MODE: Literal["auto", "native", "emulated"] = os.getenv("DB2_MODE", "auto").lower() # type: ignore
    
    # LLM Settings
    LLM_PROVIDER: Literal["gemini", "watsonx", "ollama"] = os.getenv("LLM_PROVIDER", "gemini").lower() # type: ignore
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    WATSONX_APIKEY: str = os.getenv("WATSONX_APIKEY", "")
    WATSONX_PROJECT_ID: str = os.getenv("WATSONX_PROJECT_ID", "")
    WATSONX_URL: str = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    WATSONX_MODEL_ID: str = os.getenv("WATSONX_MODEL_ID", "ibm/granite-13b-chat-v2")
    
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    
    # Vector Embeddings
    EMBEDDING_MODEL_NAME: str = os.getenv(
        "EMBEDDING_MODEL_NAME", 
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "384"))
    
    # Government Data API (data.gov.in Agmarknet)
    DATA_GOV_API_KEY: str = os.getenv("DATA_GOV_API_KEY", "")
    DATA_GOV_RESOURCE_ID: str = os.getenv("DATA_GOV_RESOURCE_ID", "9ef84268-d588-465a-a308-a864a43d0070")
    
    # Safety Limits
    QUERY_TIMEOUT_SECONDS: int = int(os.getenv("QUERY_TIMEOUT_SECONDS", "15"))
    MAX_ROWS_RETURNED: int = int(os.getenv("MAX_ROWS_RETURNED", "50"))
    
    # Path References
    DATA_DIR: Path = DATA_DIR
    DOCS_DIR: Path = DOCS_DIR
    MANDI_CSV_PATH: Path = DATA_DIR / "mandi_prices_snapshot.csv"
    EMULATOR_DB_PATH: Path = BASE_DIR / "db" / "kisan_mitra_db2.sqlite"

config = AppConfig()
