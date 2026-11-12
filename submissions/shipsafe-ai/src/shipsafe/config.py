"""Configuration management for ShipSafe AI.

All settings come from environment variables (optionally loaded from a local
`.env` file). Credentials are never hardcoded. `ShipSafeConfig.validate()`
fails fast on invalid values at startup.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

PACKAGE_ROOT = Path(__file__).resolve().parents[2]  # source checkout root (fixtures, docs)
POLICIES_DIR = Path(__file__).resolve().parent / "team_policies"  # shipped inside the package


def env_files() -> List[Path]:
    """Settings files, highest priority first: $SHIPSAFE_ENV_FILE, ./.env, ~/.shipsafe/.env.

    The IDE launches ShipSafe inside the *user's* project, so the per-user file in
    ~/.shipsafe is what normally carries the Db2 connection."""
    candidates = []
    if os.getenv("SHIPSAFE_ENV_FILE"):
        candidates.append(Path(os.environ["SHIPSAFE_ENV_FILE"]).expanduser())
    candidates += [Path.cwd() / ".env", Path.home() / ".shipsafe" / ".env"]
    return [p for p in candidates if p.is_file()]


def _load_dotenv() -> None:
    """Load KEY=VALUE pairs without overriding real environment variables or a higher-priority file."""
    for env_file in env_files():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _list(name: str, default: str) -> List[str]:
    return [p.strip() for p in os.getenv(name, default).split(os.pathsep) if p.strip()]


def _security_from_env() -> str:
    """DB2_SSL=true|false (preferred) or DB2_SECURITY=SSL|NONE."""
    if os.getenv("DB2_SSL") is not None:
        return "SSL" if _bool("DB2_SSL", "false") else "NONE"
    return os.getenv("DB2_SECURITY", "NONE").upper()


@dataclass
class Db2Config:
    """IBM Db2 connection settings (defaults match the IBM Db2 VS Code extension's local instance)."""
    host: str = "localhost"
    port: int = 50001
    database: str = "TESTDB"
    username: str = "db2inst1"
    password: str = ""
    security: str = "NONE"
    schema: str = "SHIPSAFE"
    connect_timeout: int = 10

    def __post_init__(self) -> None:
        # "localhost" may resolve to IPv6 ::1 first, while Docker/WSL port forwards for Db2 listen on IPv4 only:
        # every connect would then wait for the IPv6 attempt to time out. Use the IPv4 loopback directly.
        if self.host.strip().lower() == "localhost":
            self.host = "127.0.0.1"

    @classmethod
    def from_env(cls, prefix: str = "DB2_") -> "Db2Config":
        return cls(
            host=os.getenv("DB2_HOST", "localhost"),
            port=int(os.getenv("DB2_PORT", "50001")),
            database=os.getenv("DB2_NAME", os.getenv("DB2_DATABASE", "TESTDB")),
            username=os.getenv(f"{prefix}USERNAME", os.getenv("DB2_USERNAME", "db2inst1")),
            password=os.getenv(f"{prefix}PASSWORD", os.getenv("DB2_PASSWORD", "")),
            security=_security_from_env(),
            schema=os.getenv("DB2_SCHEMA", "SHIPSAFE").upper(),
        )

    def connection_string(self) -> str:
        conn = (
            f"DATABASE={self.database};HOSTNAME={self.host};PORT={self.port};"
            f"PROTOCOL=TCPIP;UID={self.username};PWD={self.password};CONNECTTIMEOUT={int(self.connect_timeout)};"
        )
        if self.security == "SSL":
            conn += "SECURITY=SSL;"
        return conn


@dataclass
class LlmConfig:
    """Local IBM Granite models served by Ollama."""
    host: str = "http://localhost:11434"
    chat_model: str = "granite4:micro"
    embed_model: str = "granite-embedding:30m"
    embed_dimension: int = 384
    timeout_s: int = 180
    temperature: float = 0.1

    @classmethod
    def from_env(cls) -> "LlmConfig":
        return cls(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/"),
            chat_model=os.getenv("SHIPSAFE_CHAT_MODEL", "granite4:micro"),
            embed_model=os.getenv("SHIPSAFE_EMBED_MODEL", "granite-embedding:30m"),
            embed_dimension=int(os.getenv("SHIPSAFE_VECTOR_DIMENSION", "384")),
            timeout_s=int(os.getenv("SHIPSAFE_LLM_TIMEOUT", "180")),
            temperature=float(os.getenv("SHIPSAFE_LLM_TEMPERATURE", "0.1")),
        )


@dataclass
class ShipSafeConfig:
    """Master configuration for ShipSafe AI."""
    env: str = "development"
    db2: Db2Config = field(default_factory=Db2Config.from_env)
    llm: LlmConfig = field(default_factory=LlmConfig.from_env)
    enable_mcp: bool = True
    embedding_provider: str = "ollama"         # ollama (Granite, default) | hashing (no-model fallback)
    embedding_dimension: int = 384
    policies_dir: str = str(POLICIES_DIR)
    # Scanners
    use_bandit: bool = True
    pip_audit: str = "deep"                    # deep (deep profile only) | always | off
    # API server
    api_host: str = "127.0.0.1"
    api_port: int = 8080
    auth_enabled: bool = True
    cors_origins: List[str] = field(default_factory=list)
    allowed_roots: List[str] = field(default_factory=lambda: [str(PACKAGE_ROOT / "fixtures")])
    pool_size: int = 4
    max_concurrent_scans: int = 2
    scan_rate_per_minute: int = 10
    log_format: str = "text"                   # text | json
    log_level: str = "INFO"

    @classmethod
    def load(cls) -> "ShipSafeConfig":
        return cls(
            env=os.getenv("SHIPSAFE_ENV", "development"),
            db2=Db2Config.from_env(),
            llm=LlmConfig.from_env(),
            enable_mcp=_bool("SHIPSAFE_ENABLE_MCP", "true"),
            embedding_provider=os.getenv("SHIPSAFE_EMBEDDINGS", "ollama").lower(),
            embedding_dimension=int(os.getenv("SHIPSAFE_VECTOR_DIMENSION", "384")),
            policies_dir=os.getenv("SHIPSAFE_POLICIES_DIR", str(POLICIES_DIR)),
            use_bandit=_bool("SHIPSAFE_BANDIT", "true"),
            pip_audit=os.getenv("SHIPSAFE_PIP_AUDIT", "deep").lower(),
            api_host=os.getenv("SHIPSAFE_API_HOST", "127.0.0.1"),
            api_port=int(os.getenv("SHIPSAFE_API_PORT", "8080")),
            auth_enabled=_bool("SHIPSAFE_AUTH", "true"),
            cors_origins=_list("SHIPSAFE_CORS_ORIGINS", ""),
            allowed_roots=_list("SHIPSAFE_ALLOWED_ROOTS", str(PACKAGE_ROOT / "fixtures")),
            pool_size=int(os.getenv("SHIPSAFE_DB_POOL_SIZE", "4")),
            max_concurrent_scans=int(os.getenv("SHIPSAFE_MAX_CONCURRENT_SCANS", "2")),
            scan_rate_per_minute=int(os.getenv("SHIPSAFE_SCAN_RATE_PER_MINUTE", "10")),
            log_format=os.getenv("SHIPSAFE_LOG_FORMAT", "text").lower(),
            log_level=os.getenv("SHIPSAFE_LOG_LEVEL", "INFO").upper(),
        )

    def validate(self) -> List[str]:
        """Return a list of configuration problems (empty when valid)."""
        problems = []
        if not self.db2.password:
            problems.append("DB2_PASSWORD is not set")
        if self.embedding_provider not in ("ollama", "hashing"):
            problems.append("SHIPSAFE_EMBEDDINGS must be ollama or hashing")
        if not self.llm.host.startswith(("http://", "https://")):
            problems.append("OLLAMA_HOST must start with http:// or https://")
        if self.db2.security not in ("NONE", "SSL"):
            problems.append("DB2_SECURITY must be NONE or SSL")
        if not self.db2.schema.replace("_", "").isalnum():
            problems.append("DB2_SCHEMA must contain only letters, digits and underscores")
        if self.pip_audit not in ("deep", "always", "off"):
            problems.append("SHIPSAFE_PIP_AUDIT must be deep, always or off")
        if self.log_format not in ("text", "json"):
            problems.append("SHIPSAFE_LOG_FORMAT must be text or json")
        if not 1 <= self.pool_size <= 32:
            problems.append("SHIPSAFE_DB_POOL_SIZE must be between 1 and 32")
        if not self.auth_enabled and self.api_host not in ("127.0.0.1", "localhost", "::1"):
            problems.append("SHIPSAFE_AUTH=false is only allowed when the API binds to localhost")
        return problems
