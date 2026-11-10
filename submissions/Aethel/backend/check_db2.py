"""Verify that the configured IBM Db2 service is reachable and responds to a ping."""
from pathlib import Path

from dotenv import load_dotenv

from backend.companion.db import Db2Store, Db2UnavailableError


if __name__ == "__main__":
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    store = Db2Store()
    if not store.is_configured:
        raise SystemExit(
            "Db2 is not configured. Set DB2_HOST, DB2_PORT, DB2_DATABASE, DB2_USER, and DB2_PASSWORD in .env."
        )
    try:
        if not store.ping():
            raise SystemExit("Db2 ping did not return the expected result.")
    except Db2UnavailableError as exc:
        raise SystemExit(f"Db2 verification failed: {exc}") from exc
    print("IBM Db2 connection verified successfully.")
