"""
Configuration Manager for IBM Db2 Student Notes Vector Search RAG.
Supports flexible configuration from environment variables, .env files,
and defaults tailored for IBM Db2 TechX Summit 2026.
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path


def load_env_file(dotenv_path: Optional[str] = None) -> None:
    """Safely load .env variables without external dependencies if python-dotenv is not installed."""
    if dotenv_path and os.path.isfile(dotenv_path):
        paths = [dotenv_path]
    else:
        # Search current directory, parent directory, and root workspace
        curr = Path.cwd()
        paths = [
            curr / ".env",
            curr / ".." / ".env",
            Path(__file__).resolve().parent.parent / ".env",
            Path(__file__).resolve().parent.parent.parent.parent / ".env",
        ]

    for p in paths:
        try:
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            os.environ.setdefault(k.strip(), v.strip().strip("'\""))
        except Exception:
            pass


load_env_file()


class Db2RAGConfig:
    """Unified configuration for IBM Db2 Vector Store, Embeddings, and LLMs."""

    # Db2 Connection Parameters
    DB2_DATABASE: str = os.getenv("DB2_DATABASE", "testdb")
    DB2_HOST: str = os.getenv("DB2_HOST", "localhost")
    DB2_PORT: int = int(os.getenv("DB2_PORT", "50000"))
    DB2_PROTOCOL: str = os.getenv("DB2_PROTOCOL", "TCPIP")
    DB2_USER: str = os.getenv("DB2_USER", "db2inst1")
    DB2_PASSWORD: str = os.getenv("DB2_PASSWORD", "password")
    DB2_SCHEMA: Optional[str] = os.getenv("DB2_SCHEMA", None)
    DB2_TABLE_NAME: str = os.getenv("DB2_TABLE_NAME", "STUDENT_NOTES_VS")

    # Raw connection string override if provided
    DB2_CONNECTION_STRING: str = os.getenv("DB2_CONNECTION_STRING", "")

    # Embeddings Configuration
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2"
    )
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "768"))
    DISTANCE_STRATEGY: str = os.getenv("DISTANCE_STRATEGY", "COSINE")

    # Document Chunking Settings
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "800"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "150"))

    # LLM Settings
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")  # watsonx, openai, gemini, ollama, auto, local
    WATSONX_APIKEY: str = os.getenv("WATSONX_APIKEY", "")
    WATSONX_PROJECT_ID: str = os.getenv("WATSONX_PROJECT_ID", "")
    WATSONX_URL: str = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    WATSONX_MODEL_ID: str = os.getenv("WATSONX_MODEL_ID", "ibm/granite-3-8b-instruct")

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "granite3.3:8b")

    # Retrieval Settings
    TOP_K: int = int(os.getenv("TOP_K", "4"))
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.40"))

    @classmethod
    def get_connection_string(cls) -> str:
        """Returns the formatted IBM Db2 connection string."""
        if cls.DB2_CONNECTION_STRING:
            return cls.DB2_CONNECTION_STRING
        return (
            f"DATABASE={cls.DB2_DATABASE};"
            f"HOSTNAME={cls.DB2_HOST};"
            f"PORT={cls.DB2_PORT};"
            f"PROTOCOL={cls.DB2_PROTOCOL};"
            f"UID={cls.DB2_USER};"
            f"PWD={cls.DB2_PASSWORD};"
        )

    @classmethod
    def as_dict(cls) -> Dict[str, Any]:
        """Return sanitised configuration dictionary for diagnostics."""
        return {
            "db2_database": cls.DB2_DATABASE,
            "db2_host": cls.DB2_HOST,
            "db2_port": cls.DB2_PORT,
            "db2_user": cls.DB2_USER,
            "db2_table_name": cls.DB2_TABLE_NAME,
            "embedding_model": cls.EMBEDDING_MODEL,
            "embedding_dim": cls.EMBEDDING_DIM,
            "distance_strategy": cls.DISTANCE_STRATEGY,
            "chunk_size": cls.CHUNK_SIZE,
            "chunk_overlap": cls.CHUNK_OVERLAP,
            "llm_provider": cls.LLM_PROVIDER,
            "top_k": cls.TOP_K,
        }

