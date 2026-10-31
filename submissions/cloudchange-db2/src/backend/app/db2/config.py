"""IBM Db2 Configuration and Environment Binding.

Reads IBM Db2 connection parameters from standard environment variables with
fallback defaults suitable for local development or Docker Db2 containers.
"""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Db2Config(BaseSettings):
    """Configuration settings for IBM Db2 database connectivity."""
    model_config = SettingsConfigDict(
        env_prefix="DB2_",
        case_sensitive=False,
        extra="ignore",
    )

    host: str = Field(default="localhost", description="Db2 hostname or IP address")
    port: int = Field(default=50000, description="Db2 listener port (default: 50000, SSL: 50001)")
    database: str = Field(default="BLUDB", description="Db2 database name (e.g. BLUDB, testdb)")
    user: str = Field(default="db2inst1", description="Db2 database user")
    password: str = Field(default="", description="Db2 user password")
    security: str = Field(default="", description="Security mechanism (set to 'SSL' for SSL connections)")
    schema_name: str = Field(default="CLOUDCHANGE", description="Target Db2 schema namespace")
    ssl_server_cert: Optional[str] = Field(default=None, description="Path to SSL certificate file if SSL is enabled")
    conn_timeout: int = Field(default=30, description="Connection timeout in seconds")

    @classmethod
    def from_env(cls) -> "Db2Config":
        """Build Db2Config checking DB2_* and CLOUDCHANGE_DB2_* environment variables."""
        return cls(
            host=os.getenv("DB2_HOST") or os.getenv("DB2_HOSTNAME") or os.getenv("CLOUDCHANGE_DB2_HOST", "localhost"),
            port=int(os.getenv("DB2_PORT") or os.getenv("CLOUDCHANGE_DB2_PORT", "50000")),
            database=os.getenv("DB2_DATABASE") or os.getenv("DB2_DB") or os.getenv("CLOUDCHANGE_DB2_DATABASE", "BLUDB"),
            user=os.getenv("DB2_USER") or os.getenv("DB2_UID") or os.getenv("CLOUDCHANGE_DB2_USER", "db2inst1"),
            password=os.getenv("DB2_PASSWORD") or os.getenv("DB2_PWD") or os.getenv("CLOUDCHANGE_DB2_PASSWORD", ""),
            security=os.getenv("DB2_SECURITY") or os.getenv("CLOUDCHANGE_DB2_SECURITY", ""),
            schema_name=os.getenv("DB2_SCHEMA") or os.getenv("CLOUDCHANGE_DB2_SCHEMA", "CLOUDCHANGE"),
            ssl_server_cert=os.getenv("DB2_SSL_SERVER_CERT") or os.getenv("CLOUDCHANGE_DB2_SSL_SERVER_CERT"),
            conn_timeout=int(os.getenv("DB2_TIMEOUT") or os.getenv("CLOUDCHANGE_DB2_TIMEOUT", "30")),
        )

    def get_connection_string(self) -> str:
        """Construct the official ibm_db connection string."""
        parts = [
            f"DATABASE={self.database}",
            f"HOSTNAME={self.host}",
            f"PORT={self.port}",
            "PROTOCOL=TCPIP",
            f"UID={self.user}",
            f"PWD={self.password}",
        ]
        if self.security.upper() == "SSL":
            parts.append("SECURITY=SSL")
            if self.ssl_server_cert:
                parts.append(f"SSLServerCertificate={self.ssl_server_cert}")

        return ";".join(parts) + ";"

    def is_configured(self) -> bool:
        """Return True if minimum required credentials for Db2 are provided."""
        return bool(self.host and self.database and self.user and self.password)
