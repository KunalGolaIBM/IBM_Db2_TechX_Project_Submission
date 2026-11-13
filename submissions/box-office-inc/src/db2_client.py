from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import ibm_db
except ImportError:  # pragma: no cover
    ibm_db = None

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_environment() -> None:
    if load_dotenv is None:
        return
    candidate_files = [
        PROJECT_ROOT / ".env",
        PROJECT_ROOT.parent / ".env",
    ]
    for env_file in candidate_files:
        if env_file.exists():
            load_dotenv(env_file, override=False)


load_environment()


def get_db2_config() -> Dict[str, str]:
    return {
        "host": os.getenv("DB2_HOST", ""),
        "port": os.getenv("DB2_PORT", "50000"),
        "database": os.getenv("DB2_DATABASE", ""),
        "user": os.getenv("DB2_USER", ""),
        "password": os.getenv("DB2_PASSWORD", ""),
        "dsn": os.getenv("DB2_DSN", ""),
    }


def build_connection_string() -> Optional[str]:
    config = get_db2_config()
    if config["dsn"]:
        return config["dsn"]
    if config["host"] and config["database"] and config["user"]:
        return (
            "DATABASE={database};HOSTNAME={host};PORT={port};PROTOCOL=TCPIP;"
            "UID={user};PWD={password};".format(
                database=config["database"],
                host=config["host"],
                port=config["port"],
                user=config["user"],
                password=config["password"],
            )
        )
    return None


def test_connection() -> Dict[str, Any]:
    if ibm_db is None:
        return {
            "status": "unavailable",
            "mode": "demo",
            "reason": "ibm_db is not installed in the current Python environment.",
        }

    dsn = build_connection_string()
    if not dsn:
        return {
            "status": "not_configured",
            "mode": "demo",
            "reason": "IBM Db2 environment variables are missing. Add DB2_HOST / DB2_DATABASE / DB2_USER / DB2_PASSWORD or DB2_DSN.",
        }

    conn = None
    try:
        conn = ibm_db.connect(dsn, "", "")
        stmt = ibm_db.exec_immediate(conn, "SELECT 1 FROM SYSIBM.SYSDUMMY1")
        ibm_db.fetch_tuple(stmt)
        return {
            "status": "connected",
            "mode": "live",
            "reason": "IBM Db2 connection successful.",
        }
    except Exception as exc:  # pragma: no cover
        return {
            "status": "failed",
            "mode": "demo",
            "reason": f"IBM Db2 connection failed: {type(exc).__name__}: {exc}",
        }
    finally:
        if conn is not None:
            try:
                ibm_db.close(conn)
            except Exception:
                pass


def persist_insight(studio: Dict[str, Any], recommendation: Dict[str, Any]) -> Dict[str, Any]:
    db2_status = test_connection()
    if db2_status["status"] != "connected":
        return {
            "saved": False,
            "message": "Db2 is not configured; skipping persistence.",
            "db2_status": db2_status,
        }

    conn = None
    try:
        conn = ibm_db.connect(build_connection_string(), "", "")
        try:
            ibm_db.exec_immediate(
                conn,
                (
                    "CREATE TABLE BOX_OFFICE_STUDIO_INSIGHTS ("
                    "ID INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY, "
                    "STUDIO_NAME VARCHAR(255), "
                    "REVENUE DECIMAL(18,2), "
                    "EXPENSES DECIMAL(18,2), "
                    "REPUTATION DECIMAL(10,2), "
                    "FANBASE INTEGER, "
                    "ACTIVE_MOVIES INTEGER, "
                    "MARKETING_BUDGET DECIMAL(18,2), "
                    "MARKET_TREND VARCHAR(64), "
                    "RECOMMENDATION VARCHAR(2000), "
                    "REASON VARCHAR(2000), "
                    "SOURCE VARCHAR(64), "
                    "CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    ")"
                ),
            )
        except Exception:
            pass

        insert_sql = (
            "INSERT INTO BOX_OFFICE_STUDIO_INSIGHTS ("
            "STUDIO_NAME, REVENUE, EXPENSES, REPUTATION, FANBASE, ACTIVE_MOVIES, MARKETING_BUDGET, MARKET_TREND, RECOMMENDATION, REASON, SOURCE"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        params = (
            studio.get("studio_name", "Unknown Studio"),
            float(studio.get("revenue", 0)),
            float(studio.get("expenses", 0)),
            float(studio.get("reputation", 0)),
            int(studio.get("fanbase", 0)),
            int(studio.get("active_movies", 0)),
            float(studio.get("marketing_budget", 0)),
            studio.get("market_trend", "stable"),
            recommendation.get("recommendation", ""),
            recommendation.get("reason", ""),
            recommendation.get("source", "local_fallback"),
        )
        ibm_db.execute(conn, insert_sql, params)
        return {
            "saved": True,
            "message": "Insight persisted to IBM Db2.",
            "db2_status": db2_status,
        }
    except Exception as exc:  # pragma: no cover
        return {
            "saved": False,
            "message": f"Db2 insert failed: {exc}",
            "db2_status": db2_status,
        }
    finally:
        if conn is not None:
            try:
                ibm_db.close(conn)
            except Exception:
                pass


if __name__ == "__main__":
    print(json.dumps(test_connection(), indent=2))
