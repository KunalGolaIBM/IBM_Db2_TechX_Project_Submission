import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Check for .env in current, project root, and repo root
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR.parent.parent.parent / ".env")
load_dotenv()

# IBM Db2 Enterprise Configuration
DB2_CONTAINER = os.getenv("DB2_CONTAINER", "db2server")
DB2_DATABASE = os.getenv("DB2_DATABASE", "testdb")
DB2_USER = os.getenv("DB2_USER", "db2inst1")
DB2_PASSWORD = os.getenv("DB2_PASSWORD", "")
DB2_HOST = os.getenv("DB2_HOST", "localhost")
DB2_PORT = int(os.getenv("DB2_PORT", "50000"))

# Local LM Studio LLM Endpoint
LMSTUDIO_URL = os.getenv("LMSTUDIO_URL", "http://127.0.0.1:1234/v1")
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "liquid/lfm2.5-1.2b")

# Dataset Paths (for ML training workflows)
DATA_DIR = BASE_DIR / "data"
WASTE_DATASET_PATH = DATA_DIR / "food_waste_dataset.csv"
DEMAND_DATASET_PATH = DATA_DIR / "eval.parquet"

# Models Directory (pre-trained inference weights)
MODELS_DIR = BASE_DIR / "ml" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Local SQLite Cache / Mirror path
SQLITE_DB_PATH = BASE_DIR / "smartstock.db"
