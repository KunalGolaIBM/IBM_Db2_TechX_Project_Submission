"""Production-ready clean enterprise service demonstrating IBM Db2 best practices."""

import os
from typing import Optional, Dict, Any


def get_user_profile(cursor, user_id: int) -> Optional[Dict[str, Any]]:
    """Clean parameterized query conforming to IBM Db2 security policies."""
    sql = "SELECT USER_ID, USERNAME, EMAIL FROM USERS WHERE USER_ID = ?"
    cursor.execute(sql, (user_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return {"user_id": row[0], "username": row[1], "email": row[2]}


def calculate_tax(amount: float, rate: float = 0.08) -> float:
    """Safe pure calculation function."""
    if amount < 0:
        raise ValueError("Amount cannot be negative")
    return round(amount * rate, 2)
