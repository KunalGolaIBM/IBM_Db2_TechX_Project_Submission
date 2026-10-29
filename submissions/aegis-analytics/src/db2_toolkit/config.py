"""IBM Db2 Configuration and Environment Parser for Aegis Analytics AI."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import Field

    class Db2Config(BaseSettings):
        """IBM Db2 Typed Settings."""

        model_config = SettingsConfigDict(
            env_prefix="DB2_",
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )

        database: str = Field(default="BLUDB", description="Db2 target database name")
        hostname: str = Field(default="localhost", description="Db2 hostname or IP")
        port: int = Field(default=50000, description="Db2 port (default 50000 plain, 50001 SSL)")
        protocol: str = Field(default="TCPIP", description="Db2 network protocol")
        uid: str = Field(default="db2inst1", description="Db2 username")
        pwd: str = Field(default="your_secure_password", description="Db2 password")
        security: str = Field(default="NONE", description="Security mode: NONE or SSL")
        ssl_server_cert: Optional[str] = Field(default=None, description="Path to SSL certificate")
        mock_fallback: bool = Field(default=True, description="Fallback to mock engine if offline")
        pool_size: int = Field(default=5, description="Initial connection pool size")
        max_overflow: int = Field(default=10, description="Max overflow connections")
        connection_timeout: int = Field(default=15, description="Connection timeout in seconds")
        query_timeout: int = Field(default=30, description="Query execution timeout in seconds")

        def build_connection_string(self) -> str:
            """Constructs the native ibm_db connection string."""
            conn_str = (
                f"DATABASE={self.database};"
                f"HOSTNAME={self.hostname};"
                f"PORT={self.port};"
                f"PROTOCOL={self.protocol};"
                f"UID={self.uid};"
                f"PWD={self.pwd};"
            )
            if self.security.upper() == "SSL":
                conn_str += "SECURITY=SSL;"
                if self.ssl_server_cert:
                    conn_str += f"SSLServerCertificate={self.ssl_server_cert};"
            return conn_str

        def build_sqlalchemy_url(self) -> str:
            """Constructs the SQLAlchemy connection URL."""
            ssl_param = "?Security=SSL" if self.security.upper() == "SSL" else ""
            return (
                f"db2+ibm_db://{self.uid}:{self.pwd}@"
                f"{self.hostname}:{self.port}/{self.database}{ssl_param}"
            )

except ImportError:
    from pydantic import BaseModel

    class Db2Config(BaseModel):  # type: ignore[no-redef]
        """Fallback Db2 settings without pydantic-settings."""

        database: str = "BLUDB"
        hostname: str = "localhost"
        port: int = 50000
        protocol: str = "TCPIP"
        uid: str = "db2inst1"
        pwd: str = "your_secure_password"
        security: str = "NONE"
        ssl_server_cert: Optional[str] = None
        mock_fallback: bool = True
        pool_size: int = 5
        max_overflow: int = 10
        connection_timeout: int = 15
        query_timeout: int = 30

        def build_connection_string(self) -> str:
            conn_str = (
                f"DATABASE={self.database};"
                f"HOSTNAME={self.hostname};"
                f"PORT={self.port};"
                f"PROTOCOL={self.protocol};"
                f"UID={self.uid};"
                f"PWD={self.pwd};"
            )
            if self.security.upper() == "SSL":
                conn_str += "SECURITY=SSL;"
                if self.ssl_server_cert:
                    conn_str += f"SSLServerCertificate={self.ssl_server_cert};"
            return conn_str

        def build_sqlalchemy_url(self) -> str:
            ssl_param = "?Security=SSL" if self.security.upper() == "SSL" else ""
            return (
                f"db2+ibm_db://{self.uid}:{self.pwd}@"
                f"{self.hostname}:{self.port}/{self.database}{ssl_param}"
            )


@lru_cache()
def get_db2_config() -> Db2Config:
    """Returns a cached Db2 configuration instance."""
    try:
        return Db2Config()
    except Exception:
        # Fallback to manual environment mapping if needed
        return Db2Config(
            database=os.getenv("DB2_DATABASE", "BLUDB"),
            hostname=os.getenv("DB2_HOSTNAME", "localhost"),
            port=int(os.getenv("DB2_PORT", "50000")),
            protocol=os.getenv("DB2_PROTOCOL", "TCPIP"),
            uid=os.getenv("DB2_UID", "db2inst1"),
            pwd=os.getenv("DB2_PWD", "your_secure_password"),
            security=os.getenv("DB2_SECURITY", "NONE"),
            ssl_server_cert=os.getenv("DB2_SSL_SERVER_CERT"),
            mock_fallback=os.getenv("DB2_MOCK_FALLBACK", "true").lower() in ("true", "1", "yes"),
        )

