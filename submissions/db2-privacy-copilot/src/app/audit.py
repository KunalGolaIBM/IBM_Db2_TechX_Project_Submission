"""
Hash-chained audit log for tamper detection.

Every audit record contains:
- Hash of the previous record
- Hash of its own content (actor, action, subject, detail)
- This creates a blockchain-like chain

Tampering with any record breaks the chain.

Safety assumptions:
- AUDIT_LOG table is append-only (no UPDATE/DELETE permissions)
- Hashes use SHA256
- Details contain metadata only, never PII values
"""
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from app.db import conn, query


@dataclass
class AuditRecord:
    """Single audit record."""
    
    id: int
    actor: str
    action: str
    subject: Optional[int]
    detail: dict[str, Any]
    prev_hash: str
    hash: str
    created_at: datetime


class AuditChainError(Exception):
    """Raised when audit chain verification fails."""
    pass


def compute_hash(
    prev_hash: str,
    actor: str,
    action: str,
    subject: Optional[int],
    detail: dict[str, Any],
) -> str:
    """
    Compute SHA256 hash for an audit record.
    
    The hash includes:
    - Previous record's hash (chain)
    - Actor (who)
    - Action (what)
    - Subject (patient ID if applicable)
    - Detail (JSON metadata, no PII)
    
    Args:
        prev_hash: Hash of previous record
        actor: Actor identifier (email or username)
        action: Action type (e.g., 'ERASURE', 'CLASSIFICATION', 'SCAN')
        subject: Subject ID (e.g., patient ID) or None
        detail: Dictionary of metadata (no PII values)
        
    Returns:
        SHA256 hash as hex string
    """
    # Serialize detail as sorted JSON for consistency
    detail_json = json.dumps(detail, sort_keys=True)
    
    # Build hash input
    subject_str = str(subject) if subject is not None else "NONE"
    hash_input = f"{prev_hash}{actor}{action}{subject_str}{detail_json}"
    
    # Compute hash
    return hashlib.sha256(hash_input.encode()).hexdigest()


def get_latest_hash(connection=None) -> str:
    """
    Get the hash of the most recent audit record.
    
    Returns:
        Hash string, or "GENESIS" if no records exist
    """
    if connection is not None:
        cur = connection.cursor()
        cur.execute("SELECT HASH FROM AUDIT_LOG ORDER BY ID DESC FETCH FIRST 1 ROW ONLY")
        row = cur.fetchone()
        return row[0] if row else "GENESIS"

    result = query("SELECT HASH FROM AUDIT_LOG ORDER BY ID DESC FETCH FIRST 1 ROW ONLY")
    if result:
        return result[0][0]
    
    return "GENESIS"


def append(
    actor: str,
    action: str,
    subject: Optional[int] = None,
    detail: Optional[dict[str, Any]] = None,
    connection=None,
) -> int:
    """
    Append a new audit record to the chain.
    
    Args:
        actor: Who performed the action
        action: What action was performed
        subject: Subject ID (e.g., patient ID)
        detail: Metadata dictionary (no PII values!)
        
    Returns:
        ID of the inserted audit record
        
    Raises:
        Exception: If insertion fails

    Passing an existing connection makes the audit row part of that
    connection's transaction. The caller then owns commit and rollback.
    """
    if detail is None:
        detail = {}
    
    # Get previous hash
    prev_hash = get_latest_hash(connection)
    
    # Compute new hash
    new_hash = compute_hash(prev_hash, actor, action, subject, detail)
    
    # Serialize detail
    detail_json = json.dumps(detail, sort_keys=True)
    
    # Insert record
    owns_connection = connection is None
    c = connection or conn()
    try:
        cur = c.cursor()
        cur.execute("""
            INSERT INTO AUDIT_LOG (ACTOR, ACTION, SUBJECT, DETAIL, PREV_HASH, HASH)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (actor, action, subject, detail_json, prev_hash, new_hash))
        
        # Get the inserted ID
        cur.execute("VALUES IDENTITY_VAL_LOCAL()")
        record_id = int(cur.fetchone()[0])
        
        if owns_connection:
            c.commit()
        return record_id
    finally:
        if owns_connection:
            c.close()


def get_all_records() -> list[AuditRecord]:
    """
    Retrieve all audit records in chronological order.
    
    Returns:
        List of AuditRecord objects
    """
    result = query("""
        SELECT ID, ACTOR, ACTION, SUBJECT, DETAIL, PREV_HASH, HASH, CREATED_AT
        FROM AUDIT_LOG
        ORDER BY ID ASC
    """)
    
    if not result:
        return []
    
    records = []
    for row in result:
        records.append(AuditRecord(
            id=row[0],
            actor=row[1],
            action=row[2],
            subject=row[3],
            detail=json.loads(row[4]) if row[4] else {},
            prev_hash=row[5],
            hash=row[6],
            created_at=row[7],
        ))
    
    return records


def verify_chain() -> tuple[bool, Optional[str]]:
    """
    Verify the integrity of the entire audit chain.
    
    Checks:
    1. First record has PREV_HASH = 'GENESIS'
    2. Each subsequent record's PREV_HASH matches the previous record's HASH
    3. Each record's HASH is correctly computed from its content
    
    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if chain is intact
        - (False, error_message) if tampering detected
    """
    records = get_all_records()
    
    if not records:
        return True, None
    
    # Check first record
    if records[0].prev_hash != "GENESIS":
        return False, f"First record (ID={records[0].id}) does not start with GENESIS"
    
    # Verify each record
    for i, record in enumerate(records):
        is_genesis_anchor = (
            i == 0
            and record.action == "GENESIS"
            and record.prev_hash == "GENESIS"
            and record.hash == "GENESIS"
        )
        if not is_genesis_anchor:
            expected_hash = compute_hash(
                record.prev_hash,
                record.actor,
                record.action,
                record.subject,
                record.detail,
            )

            if expected_hash != record.hash:
                return False, (
                    f"Record ID={record.id} has incorrect hash. "
                    f"Expected {expected_hash}, got {record.hash}"
                )
        
        # Check chain (except for first record)
        if i > 0:
            prev_record = records[i - 1]
            if record.prev_hash != prev_record.hash:
                return False, (
                    f"Chain broken at record ID={record.id}. "
                    f"PREV_HASH={record.prev_hash} does not match "
                    f"previous record's HASH={prev_record.hash}"
                )
    
    return True, None


def get_records_by_action(action: str) -> list[AuditRecord]:
    """
    Get all audit records for a specific action type.
    
    Args:
        action: Action type to filter by
        
    Returns:
        List of matching audit records
    """
    result = query("""
        SELECT ID, ACTOR, ACTION, SUBJECT, DETAIL, PREV_HASH, HASH, CREATED_AT
        FROM AUDIT_LOG
        WHERE ACTION = ?
        ORDER BY ID ASC
    """, (action,))
    
    if not result:
        return []
    
    records = []
    for row in result:
        records.append(AuditRecord(
            id=row[0],
            actor=row[1],
            action=row[2],
            subject=row[3],
            detail=json.loads(row[4]) if row[4] else {},
            prev_hash=row[5],
            hash=row[6],
            created_at=row[7],
        ))
    
    return records


def get_records_by_subject(subject_id: int) -> list[AuditRecord]:
    """
    Get all audit records for a specific subject (e.g., patient).
    
    Args:
        subject_id: Subject ID
        
    Returns:
        List of matching audit records
    """
    result = query("""
        SELECT ID, ACTOR, ACTION, SUBJECT, DETAIL, PREV_HASH, HASH, CREATED_AT
        FROM AUDIT_LOG
        WHERE SUBJECT = ?
        ORDER BY ID ASC
    """, (subject_id,))
    
    if not result:
        return []
    
    records = []
    for row in result:
        records.append(AuditRecord(
            id=row[0],
            actor=row[1],
            action=row[2],
            subject=row[3],
            detail=json.loads(row[4]) if row[4] else {},
            prev_hash=row[5],
            hash=row[6],
            created_at=row[7],
        ))
    
    return records


if __name__ == "__main__":
    """Demonstrate audit chain functionality."""
    print("=" * 60)
    print("Audit Chain Demo")
    print("=" * 60)
    
    # Append some test records
    print("\n1. Appending test audit records...")
    
    id1 = append(
        actor="system",
        action="TEST_START",
        detail={"test": "audit chain demo"}
    )
    print(f"   Record {id1} created")
    
    id2 = append(
        actor="alice@example.com",
        action="CLASSIFICATION",
        detail={"schema": "DB2INST1", "columns_classified": 42}
    )
    print(f"   Record {id2} created")
    
    id3 = append(
        actor="bob@example.com",
        action="ERASURE",
        subject=123,
        detail={"tables": ["PATIENT", "APPOINTMENT"], "rows_deleted": 15}
    )
    print(f"   Record {id3} created")
    
    # Verify chain
    print("\n2. Verifying audit chain...")
    is_valid, error = verify_chain()
    
    if is_valid:
        print("   ✓ Chain is INTACT")
    else:
        print(f"   ✗ Chain is BROKEN: {error}")
    
    # Show records
    print("\n3. Recent audit records:")
    records = get_all_records()[-5:]  # Last 5 records
    for r in records:
        print(f"   ID={r.id}, Actor={r.actor}, Action={r.action}, "
              f"Hash={r.hash[:16]}...")
    
    # Filter by action
    print("\n4. Erasure records:")
    erasures = get_records_by_action("ERASURE")
    for r in erasures[-3:]:  # Last 3
        print(f"   Subject={r.subject}, Detail={r.detail}")
    
    print("\n" + "=" * 60)
    print("Demo complete - chain verified!")
    print("=" * 60)
    print("\nTo test tampering:")
    print("  1. Run: db2 connect to clinic")
    print("  2. Run: db2 \"UPDATE AUDIT_LOG SET DETAIL='hacked' WHERE ID=<some_id>\"")
    print("  3. Run this script again to see chain break")
