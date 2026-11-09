"""
GitMind 2.0 — Central Configuration

Loads environment variables and provides factory functions for
LLM models, embedding models, IBM Db2 persistence, and project-wide settings.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Search order for .env:
# 1. Current working directory
# 2. Project root (dev)
# 3. tests/ (dev fallback)
# 4. ~/.gitmind/.env (pip install fallback, protected against permission errors)
_project_root = Path(__file__).resolve().parent

_candidate_paths = [
    Path.cwd() / ".env",
    _project_root / ".env",
    _project_root / "tests" / ".env",
]

try:
    _gitmind_home = Path.home() / ".gitmind"
    _candidate_paths.append(_gitmind_home / ".env")
except Exception:
    _gitmind_home = _project_root / ".gitmind_cache"

for _env_path in _candidate_paths:
    try:
        if _env_path.is_file():
            load_dotenv(_env_path, override=False)
            break
    except Exception:
        continue

# ---------------------------------------------------------------------------
# Storage & Database Configuration
# ---------------------------------------------------------------------------
STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "db2").lower()

DB2_DATABASE: str = os.getenv("DB2_DATABASE", "BLUDB")
DB2_HOST: str = os.getenv("DB2_HOST", "localhost")
DB2_PORT: int = int(os.getenv("DB2_PORT", "50001"))
DB2_USERNAME: str = os.getenv("DB2_USERNAME", "")
DB2_PASSWORD: str = os.getenv("DB2_PASSWORD", "")
DB2_SSL: bool = os.getenv("DB2_SSL", "true").lower() in ("true", "1", "yes")
DB2_SSL_CERTIFICATE: Optional[str] = os.getenv("DB2_SSL_CERTIFICATE", None)

DB2_SCHEMA: str = os.getenv("DB2_SCHEMA", "GITMIND").upper()
DB2_VECTOR_TABLE: str = os.getenv("DB2_VECTOR_TABLE", "GITMIND_VECTORS").upper()

# ---------------------------------------------------------------------------
# LLM & Embedding Providers
# ---------------------------------------------------------------------------
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower()
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", LLM_PROVIDER).lower()
EMBEDDING_MODEL: str = os.getenv(
    "EMBEDDING_MODEL",
    "models/gemini-embedding-001" if EMBEDDING_PROVIDER == "gemini" else "text-embedding-3-small",
)
_dim_env = os.getenv("EMBEDDING_DIMENSION", "")
EMBEDDING_DIMENSION: Optional[int] = int(_dim_env) if _dim_env.isdigit() else None

# ---------------------------------------------------------------------------
# Observability & Tracing
# ---------------------------------------------------------------------------
LANGSMITH_TRACING: bool = os.getenv("LANGSMITH_TRACING", "false").lower() in ("true", "1", "yes")
LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_ENDPOINT: str = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "gitmind-2.0")

if LANGSMITH_TRACING and LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGCHAIN_ENDPOINT"] = LANGSMITH_ENDPOINT
    os.environ["LANGCHAIN_PROJECT"] = LANGSMITH_PROJECT

# ---------------------------------------------------------------------------
# Local Legacy / Cache Paths
# ---------------------------------------------------------------------------
try:
    GITMIND_HOME = Path.home() / ".gitmind"
    GITMIND_HOME.mkdir(parents=True, exist_ok=True)
except Exception:
    GITMIND_HOME = _project_root / ".gitmind_cache"
    GITMIND_HOME.mkdir(parents=True, exist_ok=True)

DB_PATH = GITMIND_HOME / "gitmind.db"
CHROMA_PATH = GITMIND_HOME / "chroma"


# ---------------------------------------------------------------------------
# Factory Functions
# ---------------------------------------------------------------------------
def get_llm(temperature: float = 0, streaming: bool = False):
    """
    Factory: returns a LangChain ChatModel based on LLM_PROVIDER.

    Supports:
        - "gemini"  -> ChatGoogleGenerativeAI
        - "openai"  -> ChatOpenAI
    """
    if LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=GEMINI_API_KEY or None,
            temperature=temperature,
            streaming=streaming,
            max_retries=2,
            timeout=30,
        )

    elif LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=OPENAI_MODEL,
            api_key=OPENAI_API_KEY or None,
            temperature=temperature,
            streaming=streaming,
            max_retries=2,
            timeout=30,
        )

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{LLM_PROVIDER}'. "
            "Set LLM_PROVIDER to 'gemini' or 'openai' in your .env file."
        )


def get_embeddings():
    """
    Factory: returns a LangChain Embeddings model based on EMBEDDING_PROVIDER.
    """
    if EMBEDDING_PROVIDER == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        kwargs = {
            "model": EMBEDDING_MODEL,
            "google_api_key": GEMINI_API_KEY or None,
        }
        dim = EMBEDDING_DIMENSION or 768
        kwargs["output_dimensionality"] = dim
        return GoogleGenerativeAIEmbeddings(**kwargs)

    elif EMBEDDING_PROVIDER == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY or None,
        )

    else:
        raise ValueError(
            f"Unknown EMBEDDING_PROVIDER: '{EMBEDDING_PROVIDER}'. "
            "Set EMBEDDING_PROVIDER to 'gemini' or 'openai' in your .env file."
        )


def get_embedding_dimension() -> int:
    """
    Determine embedding dimension dynamically or from configured setting.
    """
    if EMBEDDING_DIMENSION is not None and EMBEDDING_DIMENSION > 0:
        return EMBEDDING_DIMENSION

    # Infer default dimension by model name
    model_name = EMBEDDING_MODEL.lower()
    if "text-embedding-3-small" in model_name:
        return 1536
    elif "text-embedding-3-large" in model_name:
        return 3072
    elif "text-embedding-ada-002" in model_name:
        return 1536
    elif "gemini-embedding-001" in model_name or "text-embedding-004" in model_name:
        return 768

    # Probe embedding model once
    try:
        embeddings = get_embeddings()
        vec = embeddings.embed_query("probe")
        return len(vec)
    except Exception:
        # Fallback to standard dimension
        return 768


def has_github_token() -> bool:
    """Check if a GitHub token is configured."""
    return bool(GITHUB_TOKEN and GITHUB_TOKEN not in ("your-github-token", "enter your token"))


def has_llm_api_key() -> bool:
    """Check if a valid LLM API key is configured."""
    key = GEMINI_API_KEY if LLM_PROVIDER == "gemini" else OPENAI_API_KEY
    return bool(key and not key.startswith("your-") and key not in ("TODO", "enter-key"))


def has_embedding_api_key() -> bool:
    """Check if a valid Embeddings API key is configured."""
    key = GEMINI_API_KEY if EMBEDDING_PROVIDER == "gemini" else OPENAI_API_KEY
    return bool(key and not key.startswith("your-") and key not in ("TODO", "enter-key"))


