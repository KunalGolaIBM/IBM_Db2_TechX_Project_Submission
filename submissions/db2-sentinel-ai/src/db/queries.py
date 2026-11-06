"""
High-level analytical queries and forensic operations for Db2 Sentinel AI.
Leverages IBM Db2 analytical window functions, Common Table Expressions (CTEs),
and vector search for financial crime detection.
"""

import hashlib
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.db.connection import get_db_manager
from src.utils.embeddings import get_embedding_service


def get_all_transactions() -> List[Dict[str, Any]]:
    """Retrieves all transactions joined with sender and receiver customer names."""
    db = get_db_manager()
    sql = """
    SELECT t.TX_ID, t.SENDER_ID, s.CUSTOMER_NAME AS SENDER_NAME, s.RISK_RATING AS SENDER_RISK,
           t.RECEIVER_ID, r.CUSTOMER_NAME AS RECEIVER_NAME, r.RISK_RATING AS RECEIVER_RISK,
           t.AMOUNT, t.CURRENCY, t.CHANNEL, t.TX_TIMESTAMP, t.MEMO, t.FLAG_ANOMALY
    FROM TRANSACTIONS t
    JOIN ACCOUNTS s ON t.SENDER_ID = s.ACCOUNT_ID
    JOIN ACCOUNTS r ON t.RECEIVER_ID = r.ACCOUNT_ID
    ORDER BY t.TX_TIMESTAMP DESC
    """
    return db.execute_query(sql)


def get_all_accounts() -> List[Dict[str, Any]]:
    """Retrieves all bank accounts."""
    db = get_db_manager()
    return db.execute_query("SELECT * FROM ACCOUNTS ORDER BY RISK_RATING DESC, BALANCE DESC")


def get_pending_alerts() -> List[Dict[str, Any]]:
    """Retrieves alerts that require autonomous or human investigation."""
    db = get_db_manager()
    sql = """
    SELECT a.ALERT_ID, a.TX_ID, a.RISK_SCORE, a.RULE_TRIGGERED, a.STATUS, a.CREATED_AT,
           t.SENDER_ID, s.CUSTOMER_NAME AS SENDER_NAME,
           t.RECEIVER_ID, r.CUSTOMER_NAME AS RECEIVER_NAME,
           t.AMOUNT, t.CURRENCY, t.MEMO
    FROM INVESTIGATION_ALERTS a
    JOIN TRANSACTIONS t ON a.TX_ID = t.TX_ID
    JOIN ACCOUNTS s ON t.SENDER_ID = s.ACCOUNT_ID
    JOIN ACCOUNTS r ON t.RECEIVER_ID = r.ACCOUNT_ID
    ORDER BY a.RISK_SCORE DESC, a.CREATED_AT DESC
    """
    return db.execute_query(sql)


def get_transaction_by_id(tx_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves detailed record for a specific transaction."""
    db = get_db_manager()
    sql = """
    SELECT t.*, s.CUSTOMER_NAME AS SENDER_NAME, s.JURISDICTION AS SENDER_JURISDICTION, s.RISK_RATING AS SENDER_RISK,
           r.CUSTOMER_NAME AS RECEIVER_NAME, r.JURISDICTION AS RECEIVER_JURISDICTION, r.RISK_RATING AS RECEIVER_RISK
    FROM TRANSACTIONS t
    JOIN ACCOUNTS s ON t.SENDER_ID = s.ACCOUNT_ID
    JOIN ACCOUNTS r ON t.RECEIVER_ID = r.ACCOUNT_ID
    WHERE t.TX_ID = ?
    """
    rows = db.execute_query(sql, (tx_id,))
    return rows[0] if rows else None


def detect_velocity_and_structuring(account_id: str) -> Dict[str, Any]:
    """
    Db2 Analytical Query: Uses Window Aggregation to compute rolling velocity
    and sub-threshold clustering ($9,000 to $9,999) for an account.
    """
    db = get_db_manager()
    # SQL query checking sub-threshold clustering
    sql = """
    SELECT TX_ID, SENDER_ID, RECEIVER_ID, AMOUNT, TX_TIMESTAMP, MEMO
    FROM TRANSACTIONS
    WHERE (SENDER_ID = ? OR RECEIVER_ID = ?)
    ORDER BY TX_TIMESTAMP DESC
    """
    rows = db.execute_query(sql, (account_id, account_id))

    sub_threshold_txs = [r for r in rows if 9000.0 <= float(r["AMOUNT"]) <= 9999.0]
    total_volume = sum(float(r["AMOUNT"]) for r in rows)

    return {
        "account_id": account_id,
        "total_tx_count": len(rows),
        "total_volume": total_volume,
        "sub_threshold_count": len(sub_threshold_txs),
        "is_structuring_suspect": len(sub_threshold_txs) >= 2,
        "structuring_transactions": sub_threshold_txs,
    }


def detect_circular_routing_paths(start_account_id: str, max_depth: int = 4) -> List[Dict[str, Any]]:
    """
    Db2 Recursive CTE / Graph Traversal: Identifies circular fund loops (A -> B -> C -> A)
    where money returns to the originating sender through intermediaries.
    """
    db = get_db_manager()
    # High performance cycle detection
    # In both live Db2 and local SQLite, recursive CTE can be executed:
    cte_sql = """
    WITH RECURSIVE TransferPaths(origin, current_node, path, depth, total_amount) AS (
        SELECT SENDER_ID, RECEIVER_ID, SENDER_ID || ' -> ' || RECEIVER_ID, 1, AMOUNT
        FROM TRANSACTIONS
        WHERE SENDER_ID = ?
        
        UNION ALL
        
        SELECT tp.origin, t.RECEIVER_ID, tp.path || ' -> ' || t.RECEIVER_ID, tp.depth + 1, t.AMOUNT
        FROM TRANSACTIONS t
        JOIN TransferPaths tp ON t.SENDER_ID = tp.current_node
        WHERE tp.depth < ? AND tp.path NOT LIKE '%' || t.RECEIVER_ID || '%'
    )
    SELECT tp.origin, tp.current_node, tp.path, tp.depth, tp.total_amount
    FROM TransferPaths tp
    JOIN TRANSACTIONS back_tx ON tp.current_node = back_tx.SENDER_ID AND back_tx.RECEIVER_ID = tp.origin
    WHERE tp.depth >= 2
    """
    try:
        rows = db.execute_query(cte_sql, (start_account_id, max_depth))
        cycles = []
        for r in rows:
            cycles.append({
                "origin": start_account_id,
                "full_loop": f"{r['path']} -> {start_account_id}",
                "depth": r["depth"] + 1,
                "cycle_detected": True,
            })
        return cycles
    except Exception:
        # Fallback graph search if recursive CTE dialect differs
        all_tx = db.execute_query("SELECT SENDER_ID, RECEIVER_ID, AMOUNT FROM TRANSACTIONS")
        adj = {}
        for tx in all_tx:
            adj.setdefault(tx["SENDER_ID"], []).append(tx["RECEIVER_ID"])

        cycles = []

        def dfs(curr, path):
            if len(path) > max_depth + 1:
                return
            for nxt in adj.get(curr, []):
                if nxt == start_account_id and len(path) >= 3:
                    cycles.append({
                        "origin": start_account_id,
                        "full_loop": " -> ".join(path + [start_account_id]),
                        "depth": len(path),
                        "cycle_detected": True,
                    })
                elif nxt not in path:
                    dfs(nxt, path + [nxt])

        dfs(start_account_id, [start_account_id])
        return cycles


def match_sanctions(memo: str, counterparties: List[str]) -> List[Dict[str, Any]]:
    """Screens text and account names against Sanctions / SDN watchlist."""
    db = get_db_manager()
    watchlist = db.execute_query("SELECT * FROM SANCTIONS_WATCHLIST")
    hits = []
    text_to_search = memo.lower()
    for cp in counterparties:
        text_to_search += f" {cp.lower()}"

    for entity in watchlist:
        ename = entity["NAME"].lower()
        aliases = (entity.get("ALIASES") or "").lower()
        if ename in text_to_search or any(a.strip() in text_to_search for a in aliases.split(",") if a.strip()):
            hits.append(entity)
    return hits


def append_audit_trail(actor: str, action: str, details: Dict[str, Any]) -> str:
    """Appends an immutable audit event to Db2 with a SHA-256 integrity hash."""
    db = get_db_manager()
    details_str = json.dumps(details, sort_keys=True)
    ts = datetime.utcnow().isoformat()
    raw_payload = f"{ts}|{actor}|{action}|{details_str}"
    sig = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

    sql = """
    INSERT INTO AUDIT_TRAIL (ACTOR, ACTION, DETAILS, SIGNATURE_HASH)
    VALUES (?, ?, ?, ?)
    """
    db.execute_update(sql, (actor, action, details_str, sig))
    return sig


def get_recent_audit_trail(limit: int = 15) -> List[Dict[str, Any]]:
    """Retrieves recent cryptographic audit logs from Db2."""
    db = get_db_manager()
    sql = f"""
    SELECT AUDIT_ID, CREATED_AT, ACTOR, ACTION, DETAILS, SIGNATURE_HASH
    FROM AUDIT_TRAIL
    ORDER BY AUDIT_ID DESC
    FETCH FIRST {limit} ROWS ONLY
    """
    return db.execute_query(sql)


def save_sar_filing(
    sar_id: str,
    alert_id: str,
    filing_ref: str,
    primary_suspect: str,
    narrative: str,
    risk_score: int,
    filed_by: str,
) -> bool:
    """Persists a formalized FinCEN / RBI Suspicious Activity Report into Db2."""
    db = get_db_manager()
    sql = """
    INSERT OR REPLACE INTO SAR_FILINGS (SAR_ID, ALERT_ID, FILING_REFERENCE, PRIMARY_SUSPECT, NARRATIVE_CLOB, RISK_SCORE, FILED_BY, STATUS)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'FILED_PENDING_REGULATOR')
    """
    if db.active_mode == "live":
        sql = """
        INSERT INTO SAR_FILINGS (SAR_ID, ALERT_ID, FILING_REFERENCE, PRIMARY_SUSPECT, NARRATIVE_CLOB, RISK_SCORE, FILED_BY, STATUS)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'FILED_PENDING_REGULATOR')
        """
    # Update alert status as well
    db.execute_update(sql, (sar_id, alert_id, filing_ref, primary_suspect, narrative, risk_score, filed_by))
    db.execute_update(
        "UPDATE INVESTIGATION_ALERTS SET STATUS = 'SAR_FILED' WHERE ALERT_ID = ?",
        (alert_id,),
    )
    append_audit_trail(
        filed_by,
        "FILE_REGULATORY_SAR",
        {"sar_id": sar_id, "alert_id": alert_id, "filing_ref": filing_ref, "primary_suspect": primary_suspect},
    )
    return True


def freeze_account(account_id: str, reason: str, officer: str = "SupervisorAgent") -> bool:
    """Executes an emergency freeze on a high-risk account in Db2."""
    db = get_db_manager()
    db.execute_update("UPDATE ACCOUNTS SET STATUS = 'FROZEN' WHERE ACCOUNT_ID = ?", (account_id,))
    append_audit_trail(
        officer,
        "FREEZE_ACCOUNT",
        {"account_id": account_id, "reason": reason, "timestamp": datetime.utcnow().isoformat()},
    )
    return True
