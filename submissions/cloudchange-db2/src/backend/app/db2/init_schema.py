"""CLI Tool for Initializing CloudChange Schema in IBM Db2."""

import sys
import logging
from backend.app.db2.config import Db2Config
from backend.app.db2.connection import Db2ConnectionManager
from backend.app.db2.schema import init_db2_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("db2_init")


def main() -> int:
    """CLI Entry point to initialize IBM Db2 tables and indexes."""
    config = Db2Config.from_env()
    print("=" * 60)
    print("CloudChange IBM Db2 Schema Initializer")
    print("=" * 60)
    print(f"Target Host:     {config.host}:{config.port}")
    print(f"Target Database: {config.database}")
    print(f"Target User:     {config.user}")
    print(f"Target Schema:   {config.schema_name}")
    print(f"SSL Enabled:     {bool(config.security.upper() == 'SSL')}")
    print("-" * 60)

    cm = Db2ConnectionManager(config)
    try:
        print("Connecting to IBM Db2...")
        conn = cm.connect()
        print("Connection successful! Initializing tables and indexes...")
        init_db2_schema(conn=conn, connection_manager=cm, schema_name=config.schema_name)
        cm.close(conn)
        print("✅ Schema initialization completed successfully!")
        return 0
    except Exception as exc:
        print(f"❌ Schema initialization failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
