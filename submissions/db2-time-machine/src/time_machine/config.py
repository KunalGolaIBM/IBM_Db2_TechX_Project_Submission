"""Runtime configuration, read from environment variables (and an optional .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: str | os.PathLike | None = None) -> None:
    """Tiny .env loader (KEY=VALUE lines). Existing environment variables win."""
    candidates = [Path(path)] if path else [Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        for raw in candidate.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        return


@dataclass(frozen=True)
class Settings:
    db_host: str = "localhost"
    db_port: int = 50000
    db_name: str = "TMDB"
    db_user: str = "db2inst1"
    db_password: str = ""
    db_schema: str = "TIMEMACHINE"
    db_driver: str = "ibm_db"  # "ibm_db" (native DB-API) or "sqlalchemy" (ibm_db_sa)

    llm_provider: str = "auto"  # auto | anthropic | openai | offline
    llm_model: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    max_rows: int = 500  # hard row limit appended to every read-only query
    max_iterations: int = 4  # bound on the Detective -> Verifier retry loop
    confirm_share: float = 0.60  # a hypothesis must explain >= this share of the change

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        g = os.environ.get
        return cls(
            db_host=g("DB2_HOST", "localhost"),
            db_port=int(g("DB2_PORT", "50000")),
            db_name=g("DB2_DATABASE", "TMDB"),
            db_user=g("DB2_USER", "db2inst1"),
            db_password=g("DB2_PASSWORD", ""),
            db_schema=g("DB2_SCHEMA", "TIMEMACHINE").upper(),
            db_driver=g("DB2_DRIVER", "ibm_db").lower(),
            llm_provider=g("LLM_PROVIDER", "auto").lower(),
            llm_model=g("LLM_MODEL", ""),
            anthropic_api_key=g("ANTHROPIC_API_KEY", ""),
            openai_api_key=g("OPENAI_API_KEY", ""),
            openai_base_url=g("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            max_rows=int(g("TM_MAX_ROWS", "500")),
            max_iterations=int(g("TM_MAX_ITERATIONS", "4")),
            confirm_share=float(g("TM_CONFIRM_SHARE", "0.60")),
        )
