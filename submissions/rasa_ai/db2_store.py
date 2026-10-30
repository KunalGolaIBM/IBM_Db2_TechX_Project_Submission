"""Optional Db2 persistence layer for RASA AI audition records.

Configuration is read from environment variables; credentials should never be
hard-coded in source control. The existing JSON library remains untouched.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

try:
    import ibm_db
except ImportError:  # Keep RASA AI usable when the optional driver is not installed.
    ibm_db = None

TABLE_NAME = "RASA_AUDITIONS"


def _config_value(name: str, default: str = "") -> str:
    """Read config from environment first, then local Streamlit Secrets."""
    value = os.getenv(name, "").strip()
    if value:
        return value

    # Keep this module usable outside Streamlit, too.
    try:
        import streamlit as st
        secret_value = st.secrets.get(name, default)
    except Exception:
        secret_value = default
    return str(secret_value).strip()


def _required_config() -> dict[str, str]:
    keys = {
        "host": "DB2_HOST",
        "port": "DB2_PORT",
        "database": "DB2_DATABASE",
        "user": "DB2_USER",
        "password": "DB2_PASSWORD",
    }
    config = {field: _config_value(env_name) for field, env_name in keys.items()}
    config["port"] = config["port"] or "50000"
    missing = [keys[field] for field, value in config.items() if not value]
    if missing:
        raise ValueError("Missing Db2 configuration: " + ", ".join(missing))
    return config


def _connect():
    if ibm_db is None:
        raise RuntimeError(
            "The optional Db2 driver is not installed. Install it with: python -m pip install ibm_db"
        )
    config = _required_config()
    parts = [
        f"DATABASE={config['database']}",
        f"HOSTNAME={config['host']}",
        f"PORT={config['port']}",
        "PROTOCOL=TCPIP",
        f"UID={config['user']}",
        f"PWD={config['password']}",
    ]
    if _config_value("DB2_SSL", "false").lower() in {"1", "true", "yes", "on"}:
        parts.append("SECURITY=SSL")
    connection = ibm_db.connect(";".join(parts) + ";", "", "")
    return connection


def connection_status() -> str:
    connection = _connect()
    try:
        statement = ibm_db.exec_immediate(connection, "VALUES CURRENT SERVER")
        row = ibm_db.fetch_tuple(statement)
        return f"Connected to Db2 server: {row[0] if row else 'connection established'}"
    finally:
        ibm_db.close(connection)


def ensure_schema() -> None:
    """Create the RASA audition table if it is not already present (Db2 LUW)."""
    connection = _connect()
    try:
        check = ibm_db.exec_immediate(
            connection,
            "SELECT 1 FROM SYSCAT.TABLES "
            "WHERE TABSCHEMA = CURRENT SCHEMA AND TABNAME = 'RASA_AUDITIONS'",
        )
        if ibm_db.fetch_tuple(check):
            return
        ibm_db.exec_immediate(
            connection,
            "CREATE TABLE RASA_AUDITIONS ("
            "AUDITION_ID VARCHAR(64) NOT NULL PRIMARY KEY, "
            "ACTOR_LABEL VARCHAR(256), "
            "CHARACTER_NAME VARCHAR(256), "
            "REVIEW_STATUS VARCHAR(64), "
            "SHORTLISTED SMALLINT NOT NULL DEFAULT 0, "
            "PAYLOAD CLOB(2M) NOT NULL, "
            "UPDATED_AT TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP"
            ")",
        )
    finally:
        ibm_db.close(connection)


def _record_id(item: dict[str, Any]) -> str:
    for key in ("audition_id", "id", "record_id"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)[:64]
    canonical = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sync_auditions(items: list[dict[str, Any]]) -> int:
    """Upsert JSON-library records into Db2; never deletes Db2 rows."""
    ensure_schema()
    connection = _connect()
    sql = (
        "MERGE INTO RASA_AUDITIONS AS T "
        "USING (VALUES (?, ?, ?, ?, ?, ?)) AS S "
        "(AUDITION_ID, ACTOR_LABEL, CHARACTER_NAME, REVIEW_STATUS, SHORTLISTED, PAYLOAD) "
        "ON T.AUDITION_ID = S.AUDITION_ID "
        "WHEN MATCHED THEN UPDATE SET "
        "ACTOR_LABEL = S.ACTOR_LABEL, CHARACTER_NAME = S.CHARACTER_NAME, "
        "REVIEW_STATUS = S.REVIEW_STATUS, SHORTLISTED = S.SHORTLISTED, "
        "PAYLOAD = S.PAYLOAD, UPDATED_AT = CURRENT TIMESTAMP "
        "WHEN NOT MATCHED THEN INSERT "
        "(AUDITION_ID, ACTOR_LABEL, CHARACTER_NAME, REVIEW_STATUS, SHORTLISTED, PAYLOAD, UPDATED_AT) "
        "VALUES (S.AUDITION_ID, S.ACTOR_LABEL, S.CHARACTER_NAME, S.REVIEW_STATUS, "
        "S.SHORTLISTED, S.PAYLOAD, CURRENT TIMESTAMP)"
    )
    count = 0
    try:
        statement = ibm_db.prepare(connection, sql)
        for item in items:
            if not isinstance(item, dict):
                continue
            payload = json.dumps(item, ensure_ascii=False, default=str)
            values = (
                _record_id(item),
                str(item.get("actor_label") or "")[:256],
                str(item.get("selected_character") or "")[:256],
                str(item.get("reviewer_decision") or "Not reviewed")[:64],
                1 if item.get("shortlisted", False) else 0,
                payload,
            )
            ibm_db.execute(statement, values)
            count += 1
        return count
    finally:
        ibm_db.close(connection)


def fetch_auditions(limit: int = 100) -> list[dict[str, Any]]:
    """Return recent Db2 records with their full JSON payload."""
    ensure_schema()
    limit = max(1, min(int(limit), 1000))
    connection = _connect()
    try:
        # LIMIT is supported by Db2 LUW 11.1+.
        statement = ibm_db.exec_immediate(
            connection,
            "SELECT AUDITION_ID, ACTOR_LABEL, CHARACTER_NAME, REVIEW_STATUS, "
            f"SHORTLISTED, PAYLOAD, UPDATED_AT FROM RASA_AUDITIONS ORDER BY UPDATED_AT DESC FETCH FIRST {limit} ROWS ONLY",
        )
        records = []
        row = ibm_db.fetch_assoc(statement)
        while row:
            payload = row.get("PAYLOAD")
            if isinstance(payload, str):
                try:
                    decoded = json.loads(payload)
                except json.JSONDecodeError:
                    decoded = {"payload_text": payload}
            else:
                decoded = {"payload_text": str(payload)}
            records.append({
                "audition_id": row.get("AUDITION_ID"),
                "actor_label": row.get("ACTOR_LABEL"),
                "selected_character": row.get("CHARACTER_NAME"),
                "reviewer_decision": row.get("REVIEW_STATUS"),
                "shortlisted": bool(row.get("SHORTLISTED", 0)),
                "updated_at": str(row.get("UPDATED_AT", "")),
                "payload": decoded,
            })
            row = ibm_db.fetch_assoc(statement)
        return records
    finally:
        ibm_db.close(connection)
