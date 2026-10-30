"""Shared configuration for the DevOps Runbook & Incident Assistant.

Every other script imports from here, e.g.:

    from config import get_document_store, EMBED_MODEL
"""
import os

from dotenv import load_dotenv
from haystack.utils import Secret
from haystack_integrations.document_stores.ibm_db import IBMDb2DocumentStore

load_dotenv()

OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL: str = os.getenv("EMBED_MODEL", "granite-embedding:278m")
LLM_MODEL: str = os.getenv("LLM_MODEL", "granite3.3:8b")
EMBEDDING_DIM: int = 768
TABLE_NAME: str = "runbooks"

# Granite embedding is asymmetric: only QUERIES get this prefix. Documents are
# embedded without one, so the two sides land in the space the model was trained on.
QUERY_PREFIX: str = "Represent this sentence for searching relevant passages: "


def get_document_store(recreate_table: bool = False) -> IBMDb2DocumentStore:
    """Build the Db2 document store.

    recreate_table=True drops and recreates the table (used by `ingest.py --reset`).
    """
    return IBMDb2DocumentStore(
        host=os.getenv("DB2_HOST", "localhost"),
        port=int(os.getenv("DB2_PORT", "50000")),
        database=os.getenv("DB2_DATABASE", "RUNBOOKS"),
        username=Secret.from_env_var("DB2_USERNAME"),
        password=Secret.from_env_var("DB2_PASSWORD"),
        table_name=TABLE_NAME,
        embedding_dim=EMBEDDING_DIM,
        distance_metric="COSINE",
        recreate_table=recreate_table,
    )
