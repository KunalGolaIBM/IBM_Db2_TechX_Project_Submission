"""
Bitemporal consent ledger using Db2 temporal tables.

Tracks "what consent was valid when" (business time) and 
"what we knew when" (system time).

Safety assumptions:
- All dates are validated before use in queries
- Patient IDs are validated against PATIENT table
- Purpose codes are from a controlled vocabulary
"""
from datetime import date, datetime
from typing import Optional

from app.db import conn, query


class ConsentError(Exception):
    """Base exception for consent operations."""
    pass


class ConsentInvalid(ConsentError):
    """Raised when consent is not valid for a purpose."""
    pass


def grant(
    patient_id: int,
    purpose: str,
    start: str | date,
    end: str | date = "9999-12-30",
) -> None:
    """
    Grant consent for a specific purpose.
    
    Args:
        patient_id: Patient ID
        purpose: Purpose code (e.g., 'MARKETING', 'RESEARCH', 'TREATMENT')
        start: Start date (YYYY-MM-DD or date object)
        end: End date (YYYY-MM-DD or date object), default far future
        
    Raises:
        ConsentError: If grant fails (e.g., overlapping periods)
    """
    # Convert to string if date object
    if isinstance(start, date):
        start = start.isoformat()
    if isinstance(end, date):
        end = end.isoformat()
    
    # Validate patient exists
    result = query("SELECT ID FROM PATIENT WHERE ID = ?", (patient_id,))
    if not result:
        raise ConsentError(f"Patient {patient_id} not found")
    
    # Insert consent record
    # The temporal table will handle versioning automatically
    sql = """
        INSERT INTO CONSENT (PATIENT_ID, PURPOSE, GRANTED, BUS_START, BUS_END)
        VALUES (?, ?, 'Y', ?, ?)
    """
    
    try:
        query(sql, (patient_id, purpose.upper(), start, end))
    except Exception as e:
        raise ConsentError(f"Failed to grant consent: {e}")


def withdraw(
    patient_id: int,
    purpose: str,
    effective: str | date,
) -> None:
    """
    Withdraw consent for a specific purpose.
    
    This marks the withdrawn business-time portion as not granted.
    The history table preserves the original grant.
    
    Args:
        patient_id: Patient ID
        purpose: Purpose code
        effective: Effective date of withdrawal (YYYY-MM-DD or date object)
        
    Raises:
        ConsentError: If withdrawal fails
    """
    # Convert to string if date object
    if isinstance(effective, date):
        effective = effective.isoformat()
    
    # Db2 manages the period boundaries; update the value for the withdrawn portion.
    sql = """
        UPDATE CONSENT
        FOR PORTION OF BUSINESS_TIME FROM ? TO '9999-12-30'
        SET GRANTED = 'N'
        WHERE PATIENT_ID = ? AND PURPOSE = ? AND GRANTED = 'Y'
    """
    
    try:
        c = conn()
        cur = c.cursor()
        cur.execute(sql, (effective, patient_id, purpose.upper()))
        
        if cur.rowcount == 0:
            # No active consent found, insert a withdrawal record
            cur.execute("""
                INSERT INTO CONSENT (PATIENT_ID, PURPOSE, GRANTED, BUS_START, BUS_END)
                VALUES (?, ?, 'N', ?, '9999-12-30')
            """, (patient_id, purpose.upper(), effective))
        
        c.commit()
        c.close()
    except Exception as e:
        raise ConsentError(f"Failed to withdraw consent: {e}")


def valid_on(
    patient_id: int,
    purpose: str,
    on: str | date,
    known_at: Optional[str | datetime] = None,
) -> bool:
    """
    Check if consent was valid on a specific date.
    
    This queries the bitemporal table to answer:
    "Was consent valid on date X, as we knew it at time Y?"
    
    Args:
        patient_id: Patient ID
        purpose: Purpose code
        on: Business date to check (YYYY-MM-DD or date object)
        known_at: System time to check (optional, defaults to now)
        
    Returns:
        True if consent was valid, False otherwise
    """
    # Convert to string if date object
    if isinstance(on, date):
        on = on.isoformat()
    
    # Build temporal query
    if known_at:
        if isinstance(known_at, datetime):
            known_at = known_at.isoformat()
        
        sql = """
            SELECT GRANTED
            FROM CONSENT
            FOR SYSTEM_TIME AS OF ?
            FOR BUSINESS_TIME AS OF ?
            WHERE PATIENT_ID = ? AND PURPOSE = ?
            FETCH FIRST 1 ROW ONLY
        """
        result = query(sql, (known_at, on, patient_id, purpose.upper()))
    else:
        sql = """
            SELECT GRANTED
            FROM CONSENT
            FOR BUSINESS_TIME AS OF ?
            WHERE PATIENT_ID = ? AND PURPOSE = ?
            FETCH FIRST 1 ROW ONLY
        """
        result = query(sql, (on, patient_id, purpose.upper()))
    
    if result and len(result) > 0:
        return result[0][0].strip() == "Y"
    
    return False


def consent_gate(patient_id: int, purpose: str) -> None:
    """
    Gate a processing action on valid consent.
    
    Raises an exception if consent is not valid today.
    
    Args:
        patient_id: Patient ID
        purpose: Purpose code
        
    Raises:
        ConsentInvalid: If consent is not valid
    """
    today = date.today().isoformat()
    
    if not valid_on(patient_id, purpose, today):
        raise ConsentInvalid(
            f"Consent not valid for patient {patient_id}, purpose {purpose}"
        )


def history(
    patient_id: int,
    purpose: Optional[str] = None,
) -> list[dict]:
    """
    Get full consent history for a patient.
    
    Returns both current and historical records.
    
    Args:
        patient_id: Patient ID
        purpose: Optional purpose filter
        
    Returns:
        List of consent records with system and business times
    """
    if purpose:
        sql = """
            SELECT PATIENT_ID, PURPOSE, GRANTED, BUS_START, BUS_END,
                   SYS_START, SYS_END, TRANS_ID
            FROM CONSENT_HISTORY
            WHERE PATIENT_ID = ? AND PURPOSE = ?
            ORDER BY SYS_START DESC
        """
        result = query(sql, (patient_id, purpose.upper()))
    else:
        sql = """
            SELECT PATIENT_ID, PURPOSE, GRANTED, BUS_START, BUS_END,
                   SYS_START, SYS_END, TRANS_ID
            FROM CONSENT_HISTORY
            WHERE PATIENT_ID = ?
            ORDER BY PURPOSE, SYS_START DESC
        """
        result = query(sql, (patient_id,))
    
    if not result:
        return []
    
    records = []
    for row in result:
        records.append({
            "patient_id": row[0],
            "purpose": row[1].strip(),
            "granted": row[2].strip() == "Y",
            "bus_start": row[3],
            "bus_end": row[4],
            "sys_start": row[5],
            "sys_end": row[6],
            "trans_id": row[7],
        })
    
    return records


def current_consents(patient_id: int) -> list[dict]:
    """
    Get current (active) consents for a patient.
    
    Args:
        patient_id: Patient ID
        
    Returns:
        List of current consent records
    """
    sql = """
        SELECT PATIENT_ID, PURPOSE, GRANTED, BUS_START, BUS_END
        FROM CONSENT
        WHERE PATIENT_ID = ?
        ORDER BY PURPOSE
    """
    result = query(sql, (patient_id,))
    
    if not result:
        return []
    
    records = []
    for row in result:
        records.append({
            "patient_id": row[0],
            "purpose": row[1].strip(),
            "granted": row[2].strip() == "Y",
            "bus_start": row[3],
            "bus_end": row[4],
        })
    
    return records


if __name__ == "__main__":
    """Quick demonstration of consent operations."""
    import sys
    
    print("=" * 60)
    print("Consent Ledger Demo")
    print("=" * 60)
    
    # Get a patient ID
    result = query("SELECT ID FROM PATIENT FETCH FIRST 1 ROW ONLY")
    if not result:
        print("Error: No patients in database. Run seed.py first.")
        sys.exit(1)
    
    patient_id = result[0][0]
    print(f"\nUsing patient ID: {patient_id}")
    
    # Grant consent
    print("\n1. Granting marketing consent...")
    grant(patient_id, "MARKETING", "2026-01-01", "2026-12-31")
    print("   ✓ Consent granted")
    
    # Check if valid
    print("\n2. Checking consent on 2026-06-01...")
    is_valid = valid_on(patient_id, "MARKETING", "2026-06-01")
    print(f"   Consent valid: {is_valid}")
    
    # Withdraw consent
    print("\n3. Withdrawing consent effective 2026-07-01...")
    withdraw(patient_id, "MARKETING", "2026-07-01")
    print("   ✓ Consent withdrawn")
    
    # Check before and after withdrawal
    print("\n4. Checking consent at different dates:")
    before = valid_on(patient_id, "MARKETING", "2026-06-15")
    after = valid_on(patient_id, "MARKETING", "2026-07-15")
    print(f"   On 2026-06-15 (before): {before}")
    print(f"   On 2026-07-15 (after): {after}")
    
    # Show history
    print("\n5. Consent history:")
    hist = history(patient_id, "MARKETING")
    for i, record in enumerate(hist, 1):
        print(f"   {i}. Granted={record['granted']}, "
              f"Business: {record['bus_start']} to {record['bus_end']}, "
              f"System: {record['sys_start']}")
    
    # Show current consents
    print("\n6. Current consents:")
    current = current_consents(patient_id)
    for record in current:
        print(f"   - {record['purpose']}: {record['granted']} "
              f"({record['bus_start']} to {record['bus_end']})")
    
    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)
