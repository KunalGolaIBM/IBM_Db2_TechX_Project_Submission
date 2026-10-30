"""Optional IBM Db2 + LangChain analysis for SurplusSync.

SQLite remains the operational source of truth. This router copies a minimal,
non-account listing snapshot and saved candidate evaluations to Db2, reads
that snapshot back, and grounds either a watsonx explanation or an explicitly
labelled deterministic rules-only summary in those retrieved records.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .database import connection as sqlite_connection

logger = logging.getLogger("surplussync.db2_ai")
router = APIRouter(prefix="/api/ai/db2", tags=["SurplusSync AI / IBM Db2"])
TABLE = "SURPLUSSYNC_AI_RECORDS"
DB2_REQUIRED = ("DB2_DATABASE", "DB2_HOSTNAME", "DB2_PORT", "DB2_UID", "DB2_PWD")


class AnalyzeRequest(BaseModel):
    listing_id: int = Field(gt=0)
    question: str = Field(
        default="Recommend the safest feasible food rescue option and explain why.",
        min_length=8,
        max_length=500,
    )


def _missing_db2_configuration() -> list[str]:
    if os.getenv("DB2_CONNECTION_STRING", "").strip():
        return []
    return [key for key in DB2_REQUIRED if not os.getenv(key, "").strip()]


def _connection_string() -> str:
    direct = os.getenv("DB2_CONNECTION_STRING", "").strip()
    security = os.getenv("DB2_SECURITY", "SSL").strip().upper() or "SSL"
    if security != "SSL":
        raise RuntimeError("DB2_SECURITY must be SSL for this integration.")
    if direct:
        declared_security = re.findall(r"(?:^|;)\s*SECURITY\s*=\s*([^;]*)(?=;|$)", direct, re.IGNORECASE)
        if any(value.strip().upper() != "SSL" for value in declared_security):
            raise RuntimeError("DB2_CONNECTION_STRING must use SECURITY=SSL.")
        if not declared_security:
            direct = direct.rstrip(";") + ";SECURITY=SSL;"
        return direct
    missing = _missing_db2_configuration()
    if missing:
        raise RuntimeError(
            "Set DB2_CONNECTION_STRING or all required IBM Db2 variables; missing: " + ", ".join(missing)
        )
    port = os.getenv("DB2_PORT", "").strip()
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise RuntimeError("DB2_PORT must be a valid TCP port number.")
    # Values originate in private server configuration, never from API input.
    return ";".join([
        f"DATABASE={os.environ['DB2_DATABASE'].strip()}",
        f"HOSTNAME={os.environ['DB2_HOSTNAME'].strip()}",
        f"PORT={port}",
        "PROTOCOL=TCPIP",
        f"UID={os.environ['DB2_UID'].strip()}",
        f"PWD={os.environ['DB2_PWD'].strip()}",
        "SECURITY=SSL",
        "",
    ])


def _connect():
    # Validate configuration before importing/connecting so missing settings
    # produce an actionable but non-sensitive response.
    connection_string = _connection_string()
    try:
        import ibm_db
    except ImportError as exc:
        raise RuntimeError("IBM Db2 driver is not installed. Install requirements.txt.") from exc
    return ibm_db, ibm_db.connect(connection_string, "", "")


def _ensure_table(ibm_db: Any, conn: Any) -> None:
    statement = ibm_db.exec_immediate(
        conn,
        "SELECT 1 FROM SYSCAT.TABLES WHERE TABSCHEMA = CURRENT SCHEMA "
        "AND TABNAME = 'SURPLUSSYNC_AI_RECORDS' FETCH FIRST 1 ROW ONLY",
    )
    if ibm_db.fetch_assoc(statement) is None:
        # Identifiers and schema are fixed; all record data uses parameters.
        ibm_db.exec_immediate(
            conn,
            f"""CREATE TABLE {TABLE} (
                RECORD_TYPE VARCHAR(32) NOT NULL,
                RECORD_KEY VARCHAR(120) NOT NULL,
                RECORD_JSON CLOB(1M) NOT NULL,
                UPDATED_AT TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
                PRIMARY KEY (RECORD_TYPE, RECORD_KEY)
            )""",
        )


def _delete_listing_snapshot(ibm_db: Any, conn: Any, listing_id: int) -> None:
    statement = ibm_db.prepare(conn, f"DELETE FROM {TABLE} WHERE RECORD_KEY LIKE ?")
    ibm_db.execute(statement, (f"listing:{listing_id}:%",))


def _upsert(ibm_db: Any, conn: Any, record_type: str, record_key: str, payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    select = ibm_db.prepare(
        conn,
        f"SELECT 1 FROM {TABLE} WHERE RECORD_TYPE = ? AND RECORD_KEY = ?",
    )
    ibm_db.execute(select, (record_type, record_key))
    exists = ibm_db.fetch_assoc(select) is not None
    if exists:
        statement = ibm_db.prepare(
            conn,
            f"UPDATE {TABLE} SET RECORD_JSON = ?, UPDATED_AT = CURRENT TIMESTAMP "
            "WHERE RECORD_TYPE = ? AND RECORD_KEY = ?",
        )
        ibm_db.execute(statement, (serialized, record_type, record_key))
    else:
        statement = ibm_db.prepare(
            conn,
            f"INSERT INTO {TABLE} (RECORD_TYPE, RECORD_KEY, RECORD_JSON, UPDATED_AT) "
            "VALUES (?, ?, ?, CURRENT TIMESTAMP)",
        )
        ibm_db.execute(statement, (record_type, record_key, serialized))


def _retrieve(ibm_db: Any, conn: Any, listing_id: int) -> list[dict[str, Any]]:
    statement = ibm_db.prepare(
        conn,
        f"SELECT RECORD_TYPE, RECORD_KEY, RECORD_JSON FROM {TABLE} "
        "WHERE RECORD_KEY LIKE ? ORDER BY RECORD_TYPE, RECORD_KEY",
    )
    ibm_db.execute(statement, (f"listing:{listing_id}:%",))
    records = []
    row = ibm_db.fetch_assoc(statement)
    while row:
        raw = row["RECORD_JSON"]
        if hasattr(raw, "read"):
            raw = raw.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        records.append({
            "record_type": row["RECORD_TYPE"],
            "record_key": row["RECORD_KEY"],
            "data": json.loads(raw),
        })
        row = ibm_db.fetch_assoc(statement)
    return records


def _verify_snapshot(expected: list[dict[str, Any]], retrieved: list[dict[str, Any]]) -> bool:
    expected_by_key = {item["record_key"]: item for item in expected}
    retrieved_by_key = {item["record_key"]: item for item in retrieved}
    return len(expected_by_key) == len(expected) and retrieved_by_key == expected_by_key


def _langchain_explanation(question: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate with watsonx when configured; otherwise explicitly use rules only."""
    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.runnables import RunnableLambda
    except ImportError as exc:
        raise RuntimeError("LangChain is not installed. Install requirements.txt.") from exc

    # WATSONX_API_KEY is the current IBM spelling; retain WATSONX_APIKEY for
    # existing SurplusSync configuration compatibility.
    api_key = os.getenv("WATSONX_API_KEY", "").strip() or os.getenv("WATSONX_APIKEY", "").strip()
    project_id = os.getenv("WATSONX_PROJECT_ID", "").strip()
    if api_key and project_id:
        try:
            from langchain_ibm import ChatWatsonx

            model = ChatWatsonx(
                model_id=os.getenv("WATSONX_MODEL_ID", "ibm/granite-3-3-8b-instruct"),
                url=os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"),
                apikey=api_key,
                project_id=project_id,
                params={"temperature": 0.1, "max_completion_tokens": 500},
            )
            prompt = ChatPromptTemplate.from_messages([
                (
                    "system",
                    "Explain the food-rescue decision using only the provided Db2 records. "
                    "Never certify food as safe or claim a recipient is officially verified. "
                    "Travel values are simulated. Explain category, availability, capacity, "
                    "deadline evidence and any recorded rejection reasons.",
                ),
                ("human", "Question: {question}\nRetrieved Db2 records: {context}"),
            ])
            context = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
            chain = prompt | model | RunnableLambda(lambda message: str(message.content))
            answer = chain.invoke({"question": question, "context": context})
            return {
                "answer": str(answer) + "\n\nThis explanation is not food-safety certification; human checks remain required.",
                "generation_mode": "langchain_watsonx",
                "framework": "LangChain",
                "grounding_record_count": len(records),
            }
        except Exception as exc:
            # Log only a class name: SDK exceptions can contain endpoint or config details.
            logger.warning("watsonx generation failed; exception_type=%s", type(exc).__name__)
            llm_status = f"generation_failed:{type(exc).__name__}"
    elif api_key or project_id:
        llm_status = "watsonx_credentials_incomplete"
    else:
        llm_status = "watsonx_credentials_not_configured"

    summary = RunnableLambda(lambda values: _rule_summary(values["question"], values["records"]))
    answer = summary.invoke({"question": question, "records": records})
    return {
        "answer": answer,
        "generation_mode": "rules_only",
        "framework": "LangChain RunnableLambda",
        "grounding_record_count": len(records),
        "llm_status": llm_status,
    }


def _rule_summary(question: str, records: list[dict[str, Any]]) -> str:
    listing = next((item["data"] for item in records if item["record_type"] == "LISTING"), {})
    candidates = [item["data"] for item in records if item["record_type"] == "CANDIDATE"]
    feasible = [candidate for candidate in candidates if candidate.get("feasible")]
    feasible.sort(key=lambda candidate: (
        candidate.get("rank") is None,
        candidate.get("rank", 10**9),
        candidate.get("travel_minutes", 10**9),
    ))
    if not listing:
        return "No listing snapshot was retrieved from IBM Db2; no recommendation is grounded in database evidence."
    if not feasible:
        return (
            f"No feasible recipient is present in the retrieved Db2 evaluations for listing {listing.get('id')}. "
            "Review configured capacity, availability, food category, pickup deadline, and the saved rejection "
            "reasons before proposing a rescue."
        )
    best = feasible[0]
    reasons = best.get("reasons", [])
    recipient = best.get("recipient_name") or f"recipient {best.get('recipient_id')}"
    return (
        f"For listing {listing.get('id')} ({listing.get('portions')} portions of {listing.get('food_type')}), "
        f"the highest-ranked feasible candidate in the retrieved Db2 records is {recipient} "
        f"(recipient {best.get('recipient_id')}), with a simulated travel estimate of "
        f"{best.get('travel_minutes')} minutes and {best.get('capacity_after')} portions of configured "
        f"capacity remaining. Recorded reasons: {', '.join(reasons) if reasons else 'none recorded'}. "
        "Travel values are simulated; a responsible person must complete human food-safety checks before handover."
    )


def _request_user(request: Request) -> dict[str, Any]:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(401, detail={"code": "authentication_required", "message": "Please log in to continue."})
    if user.get("role") not in {"DONOR", "ADMIN"}:
        raise HTTPException(403, detail={"code": "role_forbidden", "message": "An approved donor or administrator is required."})
    if user.get("profile_status") != "approved":
        raise HTTPException(403, detail={"code": "profile_not_approved", "message": "Complete and approve your profile before using Db2 analysis."})
    return user


def _listing_snapshot(listing: Any) -> dict[str, Any]:
    # Whitelist fields. Account ids, verifier names and contact information are
    # never copied to Db2 or sent to watsonx.
    return {
        "id": listing["id"],
        "food_type": listing["food_type"],
        "portions": listing["portions"],
        "pickup_area": listing["pickup_area"],
        "deadline": listing["deadline"],
        "prepared_at": listing["prepared_at"],
        "human_checks": {
            "handling_verified": bool(listing["safety_handling"]),
            "temperature_verified": bool(listing["safety_temperature"]),
            "allergens_verified": bool(listing["safety_allergens"]),
            "packaging_verified": bool(listing["safety_packaging"]),
            "local_requirements_verified": bool(listing["safety_local_rules"]),
        },
        "demo": bool(listing["demo"]),
        "audit": bool(listing["audit"]),
    }


def _expected_records(listing_data: dict[str, Any], candidates: list[dict[str, Any]], listing_id: int) -> list[dict[str, Any]]:
    records = [{
        "record_type": "LISTING",
        "record_key": f"listing:{listing_id}:listing",
        "data": listing_data,
    }]
    for candidate in candidates:
        records.append({
            "record_type": "CANDIDATE",
            "record_key": f"listing:{listing_id}:recipient:{candidate['recipient_id']}",
            "data": candidate,
        })
    if not candidates:
        records.append({
            "record_type": "ASSESSMENT",
            "record_key": f"listing:{listing_id}:assessment",
            "data": {"status": "no_candidate_evaluations", "message": "No saved candidate evaluations were available."},
        })
    return records


def _candidate_snapshots(db: Any, evaluations: list[Any]) -> list[dict[str, Any]]:
    recipient_ids = list(dict.fromkeys(row["recipient_id"] for row in evaluations))
    if not recipient_ids:
        return []
    placeholders = ",".join("?" for _ in recipient_ids)
    recipients = {
        row["id"]: dict(row)
        for row in db.execute(
            f"SELECT id,name,area,capacity,travel_minutes,available,food_categories FROM recipients WHERE id IN ({placeholders})",
            recipient_ids,
        ).fetchall()
    }
    candidates = []
    for row in evaluations:
        try:
            reasons = json.loads(row["reasons"])
        except (TypeError, json.JSONDecodeError):
            reasons = ["Saved rejection details could not be parsed."]
        recipient = recipients.get(row["recipient_id"], {})
        try:
            categories = json.loads(recipient.get("food_categories") or "[]")
        except (TypeError, json.JSONDecodeError):
            categories = []
        candidates.append({
            "recipient_id": row["recipient_id"],
            "recipient_name": recipient.get("name"),
            "area": recipient.get("area"),
            "configured_capacity": recipient.get("capacity"),
            "available": bool(recipient.get("available", False)),
            "accepted_categories": categories,
            "feasible": bool(row["feasible"]),
            "reasons": reasons if isinstance(reasons, list) else [str(reasons)],
            "travel_minutes": row["travel_minutes"],
            "capacity_after": row["capacity_after"],
            "rank": row["rank"],
        })
    return candidates


@router.get("/status")
def db2_status(request: Request) -> dict[str, Any]:
    _request_user(request)
    missing = _missing_db2_configuration()
    watsonx_configured = bool(
        (os.getenv("WATSONX_API_KEY", "").strip() or os.getenv("WATSONX_APIKEY", "").strip())
        and os.getenv("WATSONX_PROJECT_ID", "").strip()
    )
    if missing:
        return {
            "configured": False,
            "connected": False,
            "watsonx_configured": watsonx_configured,
            "database": "IBM Db2",
            "message": "IBM Db2 is not configured. Set DB2_CONNECTION_STRING or all required DB2_* settings.",
            "missing_configuration": missing,
            "fallback": "none for this workflow",
        }
    try:
        ibm_db, conn = _connect()
        try:
            ibm_db.exec_immediate(conn, "VALUES 1")
            return {
                "configured": True,
                "connected": True,
                "watsonx_configured": watsonx_configured,
                "database": "IBM Db2",
                "table": TABLE,
            }
        finally:
            ibm_db.close(conn)
    except Exception as exc:
        logger.warning("Db2 status check failed; exception_type=%s", type(exc).__name__)
        return {
            "configured": True,
            "connected": False,
            "watsonx_configured": watsonx_configured,
            "database": "IBM Db2",
            "message": "IBM Db2 could not be reached. Check private server configuration and connectivity.",
            "error_code": type(exc).__name__,
            "fallback": "none for this workflow",
        }


@router.post("/analyze")
def analyze_listing(body: AnalyzeRequest, request: Request) -> dict[str, Any]:
    user = _request_user(request)
    with sqlite_connection() as db:
        listing = db.execute("SELECT * FROM listings WHERE id=?", (body.listing_id,)).fetchone()
        if listing is None:
            raise HTTPException(404, detail={"code": "listing_not_found", "message": "Food listing not found."})
        if user["role"] == "DONOR" and listing["donor_user_id"] != user["id"]:
            raise HTTPException(403, detail={"code": "listing_forbidden", "message": "You can analyze only listings owned by your account."})
        plan = db.execute(
            "SELECT id FROM rescue_plans WHERE listing_id=? ORDER BY id DESC LIMIT 1",
            (body.listing_id,),
        ).fetchone()
        evaluations = []
        if plan:
            evaluations = db.execute(
                """SELECT recipient_id,feasible,reasons,travel_minutes,capacity_after,rank
                   FROM candidate_evaluations WHERE plan_id=? ORDER BY rank,recipient_id""",
                (plan["id"],),
            ).fetchall()
        listing_data = _listing_snapshot(listing)
        candidates = _candidate_snapshots(db, evaluations)

    missing = _missing_db2_configuration()
    if missing:
        raise HTTPException(
            503,
            detail={
                "code": "db2_not_configured",
                "message": "IBM Db2 is not configured. Set DB2_CONNECTION_STRING or all required DB2_* settings.",
                "missing_configuration": missing,
                "fallback": "none; Db2 analysis was not run",
            },
        )

    expected = _expected_records(listing_data, candidates, body.listing_id)
    try:
        ibm_db, conn = _connect()
        try:
            _ensure_table(ibm_db, conn)
            # ibm_db connections default to autocommit. Turn it off so a failed
            # replacement cannot leave a deleted or partially written snapshot.
            ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_OFF)
            try:
                _delete_listing_snapshot(ibm_db, conn, body.listing_id)
                for record in expected:
                    _upsert(ibm_db, conn, record["record_type"], record["record_key"], record["data"])
                retrieved = _retrieve(ibm_db, conn, body.listing_id)
                if not _verify_snapshot(expected, retrieved):
                    raise RuntimeError("Db2 snapshot read-back did not match the written records.")
                ibm_db.commit(conn)
            except Exception:
                try:
                    ibm_db.rollback(conn)
                except Exception as rollback_exc:
                    logger.warning("Db2 snapshot rollback failed; exception_type=%s", type(rollback_exc).__name__)
                raise
        finally:
            ibm_db.close(conn)
    except Exception as exc:
        logger.warning("Db2 analysis failed; exception_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "db2_unavailable",
                "message": "IBM Db2 connection, write, or read-back failed. Check private server configuration and connectivity.",
                "error_code": type(exc).__name__,
                "fallback": "none; Db2 analysis was not run",
            },
        ) from exc

    try:
        explanation = _langchain_explanation(body.question, retrieved)
    except Exception as exc:
        logger.warning("LangChain analysis failed; exception_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "langchain_unavailable",
                "message": "LangChain analysis could not run. Check installed dependencies and private watsonx configuration.",
                "error_code": type(exc).__name__,
                "db2_records_retrieved": len(retrieved),
            },
        ) from exc

    return {
        "listing_id": body.listing_id,
        "database": "IBM Db2",
        "db2_write_read_verified": True,
        "records_retrieved": len(retrieved),
        "recommendation": explanation,
        "candidates_considered": len(candidates),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
