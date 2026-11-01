import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if present
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(Path.cwd() / ".env")

# Database Backend: 'db2' or 'simulated'
DB_BACKEND = os.getenv("DB_BACKEND", "db2").lower()

# IBM Db2 Connection Parameters
DB2_HOST = os.getenv("DB2_HOST", "localhost")
DB2_PORT = int(os.getenv("DB2_PORT", "50000"))
DB2_DATABASE = os.getenv("DB2_DATABASE", "testdb")
DB2_USER = os.getenv("DB2_USER", "db2inst1")
DB2_PASSWORD = os.getenv("DB2_PASSWORD", "password")
DB2_SECURITY = os.getenv("DB2_SECURITY", "")  # e.g., 'SSL'

# Scraper Settings
SCRAPER_TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", "15"))
SCRAPER_USER_AGENT = os.getenv(
    "SCRAPER_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) InternScrap-Agent/1.0"
)

def get_db2_connection_string() -> str:
    """Builds the IBM Db2 connection string for the ibm_db driver."""
    conn_str = (
        f"DATABASE={DB2_DATABASE};"
        f"HOSTNAME={DB2_HOST};"
        f"PORT={DB2_PORT};"
        f"PROTOCOL=TCPIP;"
        f"UID={DB2_USER};"
        f"PWD={DB2_PASSWORD};"
    )
    if DB2_SECURITY and DB2_SECURITY.upper() == "SSL":
        conn_str += "SECURITY=SSL;"
    return conn_str
