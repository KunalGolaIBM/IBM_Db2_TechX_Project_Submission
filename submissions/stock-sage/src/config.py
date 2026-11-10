"""Configuration manager for StockSage.

Loads configuration from environment variables and local .env file.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Path to the project root (submissions/stock-sage)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env file from project root if it exists
ENV_PATH = PROJECT_ROOT / ".env"
if ENV_PATH.is_file():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

# IBM Db2 Settings
DB2_HOST = os.getenv("DB2_HOST", "127.0.0.1")
DB2_PORT = int(os.getenv("DB2_PORT", "50000"))
DB2_DATABASE = os.getenv("DB2_DATABASE", "testdb")
DB2_USER = os.getenv("DB2_USER", "db2inst1")
DB2_PASSWORD = os.getenv("DB2_PASSWORD", "Password123!")
DB2_SECURITY = os.getenv("DB2_SECURITY", "false")

# Fallback mode for unit tests and offline testing
USE_MOCK_DB = os.getenv("USE_MOCK_DB", "false").lower() in ("true", "1", "yes")

# Gemini LLM Settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# App Settings
APP_ENV = os.getenv("APP_ENV", "development")
