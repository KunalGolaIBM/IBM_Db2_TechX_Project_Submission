import os
from dotenv import load_dotenv

load_dotenv()
DATA_BACKEND = os.getenv("DATA_BACKEND", "demo").strip().lower()
if DATA_BACKEND not in {"demo", "db2"}:
    raise ValueError("DATA_BACKEND must be 'demo' or 'db2'.")

DB2_HOST = os.getenv("DB2_HOST", "localhost")
DB2_PORT = os.getenv("DB2_PORT", "50000")
DB2_DATABASE = os.getenv("DB2_DATABASE", "BLUDB")
DB2_USER = os.getenv("DB2_USER", "db2inst1")
DB2_PASSWORD = os.getenv("DB2_PASSWORD", "")
DB2_SECURITY = os.getenv("DB2_SECURITY", "false").lower() == "true"
