import os
from dotenv import load_dotenv

load_dotenv()
DB = dict(
    database=os.getenv("DB2_DATABASE", "CORTEX"),
    host=os.getenv("DB2_HOST", "localhost"),
    port=os.getenv("DB2_PORT", "50000"),
    user=os.getenv("DB2_USER", "db2inst1"),
    password=os.getenv("DB2_PASSWORD", ""),
)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "demo")  # demo | watsonx | openai | ollama | gemini
EMBED_DIM = 384
CACHE_THRESHOLD = float(os.getenv("CACHE_THRESHOLD", "0.12"))  # cosine distance
MAX_ROWS = 200
ALLOWED_TABLES = {"CUSTOMERS", "ACCOUNTS", "TRANSACTIONS", "LOANS", "BRANCHES"}
PII_COLUMNS = {"FULL_NAME", "EMAIL"}
