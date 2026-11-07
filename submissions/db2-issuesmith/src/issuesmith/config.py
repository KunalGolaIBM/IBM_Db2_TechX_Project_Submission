"""Central configuration. Every value comes from environment variables (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
SAMPLE_LOG_DIR = DATA_DIR / "sample_logs"
KNOWLEDGE_DIR = DATA_DIR / "knowledge_base"


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env loader (no extra dependency). Existing env vars win."""
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _get(name: str, default: str = "") -> str:
    value = os.environ.get(name, default).strip()
    # Treat untouched .env.example placeholders as "not set".
    if value.lower().startswith("your_") or value.startswith("your-username/"):
        return default
    return value


@dataclass(frozen=True)
class Settings:
    # Db2
    db2_host: str
    db2_port: int
    db2_database: str
    db2_user: str
    db2_password: str
    db2_security: str
    db2_schema: str
    # Embeddings
    embedding_backend: str
    embedding_model: str
    # LLM
    llm_provider: str
    ollama_url: str
    ollama_model: str
    openai_base_url: str
    openai_api_key: str
    openai_model: str
    watsonx_url: str
    watsonx_apikey: str
    watsonx_project_id: str
    watsonx_model: str
    # GitHub
    github_token: str
    github_search_repo: str
    github_target_repo: str
    # Agent behaviour
    max_critic_rounds: int
    duplicate_distance: float

    @property
    def db2_conn_str(self) -> str:
        conn = (
            f"DATABASE={self.db2_database};HOSTNAME={self.db2_host};PORT={self.db2_port};"
            f"PROTOCOL=TCPIP;UID={self.db2_user};PWD={self.db2_password};"
        )
        if self.db2_security.lower() in {"ssl", "true"}:
            conn += "SECURITY=SSL;"
        return conn


def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        db2_host=_get("DB2_HOST", "localhost"),
        db2_port=int(_get("DB2_PORT", "50000")),
        db2_database=_get("DB2_DATABASE", "testdb"),
        db2_user=_get("DB2_USER", "db2inst1"),
        db2_password=_get("DB2_PASSWORD", ""),
        db2_security=_get("DB2_SECURITY", "false"),
        db2_schema=_get("DB2_SCHEMA", "ISSUESMITH").upper(),
        embedding_backend=_get("EMBEDDING_BACKEND", "sentence-transformers").lower(),
        embedding_model=_get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        llm_provider=_get("LLM_PROVIDER", "none").lower(),
        ollama_url=_get("OLLAMA_URL", "http://localhost:11434"),
        ollama_model=_get("OLLAMA_MODEL", "granite3.3:2b"),
        openai_base_url=_get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        openai_api_key=_get("OPENAI_API_KEY"),
        openai_model=_get("OPENAI_MODEL", "gpt-4o-mini"),
        watsonx_url=_get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"),
        watsonx_apikey=_get("WATSONX_APIKEY"),
        watsonx_project_id=_get("WATSONX_PROJECT_ID"),
        watsonx_model=_get("WATSONX_MODEL", "ibm/granite-3-3-8b-instruct"),
        github_token=_get("GITHUB_TOKEN"),
        github_search_repo=_get("GITHUB_SEARCH_REPO", "IBM/db2developerextension-about"),
        github_target_repo=_get("GITHUB_TARGET_REPO"),
        max_critic_rounds=int(_get("MAX_CRITIC_ROUNDS", "2")),
        duplicate_distance=float(_get("DUPLICATE_DISTANCE", "0.12")),
    )
