"""
Db2-Sentinel Configuration Module
Loads environment variables and manages strictly typed settings for IBM Db2 and Agentic AI.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

@dataclass(frozen=True)
class Db2Config:
    host: str = os.getenv("DB2_HOST", "localhost")
    port: int = int(os.getenv("DB2_PORT", "50000"))
    database: str = os.getenv("DB2_DATABASE", "SENTINEL")
    user: str = os.getenv("DB2_USER", "db2inst1")
    password: str = os.getenv("DB2_PASSWORD", "SentinelDb2_2026!")
    schema: str = os.getenv("DB2_SCHEMA", "DB2INST1").upper()

    @property
    def connection_string(self) -> str:
        return (
            f"DATABASE={self.database};"
            f"HOSTNAME={self.host};"
            f"PORT={self.port};"
            f"PROTOCOL=TCPIP;"
            f"UID={self.user};"
            f"PWD={self.password};"
        )

    @property
    def sqlalchemy_url(self) -> str:
        # ibm_db_sa dialect format: ibm_db_sa://user:pwd@host:port/database
        return f"ibm_db_sa://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

@dataclass(frozen=True)
class AgentConfig:
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model_name: str = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
    openai_api_base: Optional[str] = os.getenv("OPENAI_API_BASE")
    max_iterations: int = int(os.getenv("SENTINEL_MAX_ITERATIONS", "5"))
    verbose: bool = os.getenv("SENTINEL_VERBOSE", "true").lower() in ("true", "1", "yes")
    simulation_fallback: bool = os.getenv("SENTINEL_SIMULATION_FALLBACK", "true").lower() in ("true", "1", "yes")

db2_settings = Db2Config()
agent_settings = AgentConfig()

