from typing import Optional, List, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel
from app.config import settings
from app.db import db_manager

router = APIRouter(prefix="/api/internal", tags=["Internal Gateway Data & Auth"])

def verify_service_token(x_service_token: str):
    if settings.ai_service_internal_token and x_service_token != settings.ai_service_internal_token:
        raise HTTPException(status_code=401, detail="Unauthorized internal service access.")

class CreateUserRequest(BaseModel):
    user_id: str
    email: str
    full_name: str
    password_hash: str

class CreateSessionRequest(BaseModel):
    session_token_hash: str
    user_id: str
    csrf_token_hash: str
    expires_at: str
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None

class UpdateCsrfRequest(BaseModel):
    csrf_token_hash: str

@router.get("/users/by-email")
def get_user_by_email(
    email: str = Query(...),
    x_service_token: str = Header(...)
):
    verify_service_token(x_service_token)
    sql = """
        SELECT user_id, email, full_name, password_hash, is_active, created_at
        FROM FINSIGHT.USERS
        WHERE LOWER(email) = LOWER(?)
    """
    rows = db_manager.execute_query(sql, (email.strip(),))
    if not rows:
        raise HTTPException(status_code=404, detail="User not found")
    user = rows[0]
    return {
        "user_id": user["user_id"].strip(),
        "email": user["email"].strip(),
        "full_name": user["full_name"].strip(),
        "password_hash": user["password_hash"].strip() if user["password_hash"] else None,
        "is_active": bool(user["is_active"]),
        "created_at": str(user["created_at"])
    }

@router.post("/users")
def create_user(
    req: CreateUserRequest,
    x_service_token: str = Header(...)
):
    verify_service_token(x_service_token)
    # Check duplicate email
    check_sql = "SELECT user_id FROM FINSIGHT.USERS WHERE LOWER(email) = LOWER(?)"
    existing = db_manager.execute_query(check_sql, (req.email.strip(),))
    if existing:
        raise HTTPException(status_code=409, detail="User with this email already exists")

    insert_sql = """
        INSERT INTO FINSIGHT.USERS (user_id, email, full_name, password_hash, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, 1, CURRENT TIMESTAMP, CURRENT TIMESTAMP)
    """
    db_manager.execute_statement(insert_sql, (req.user_id, req.email.strip(), req.full_name.strip(), req.password_hash))

    # Create default checking account for user
    acc_id = f"acc_{req.user_id[-12:]}_chk"
    acc_sql = """
        INSERT INTO FINSIGHT.ACCOUNTS (account_id, user_id, account_name, account_type, institution_name, currency, opening_balance, created_at)
        VALUES (?, ?, 'Primary Checking', 'CHECKING', 'FinSight Bank', 'INR', 10000.00, CURRENT TIMESTAMP)
    """
    try:
        db_manager.execute_statement(acc_sql, (acc_id, req.user_id))
    except Exception:
        pass

    return {
        "user_id": req.user_id,
        "email": req.email,
        "full_name": req.full_name,
        "is_active": True
    }

@router.post("/sessions")
def create_session(
    req: CreateSessionRequest,
    x_service_token: str = Header(...)
):
    verify_service_token(x_service_token)
    insert_sql = """
        INSERT INTO FINSIGHT.USER_SESSIONS
        (session_token_hash, user_id, csrf_token_hash, user_agent, ip_address, created_at, expires_at, last_active_at)
        VALUES (?, ?, ?, ?, ?, CURRENT TIMESTAMP, CAST(? AS TIMESTAMP), CURRENT TIMESTAMP)
    """
    # Clean timestamp string: e.g. "2026-11-09 11:30:00"
    exp = req.expires_at.replace("T", " ")[:19]
    db_manager.execute_statement(
        insert_sql,
        (req.session_token_hash, req.user_id, req.csrf_token_hash, req.user_agent or "Unknown", req.ip_address or "127.0.0.1", exp)
    )
    return {"status": "CREATED", "session_token_hash": req.session_token_hash}

@router.get("/sessions/{session_token_hash}")
def get_session(
    session_token_hash: str,
    x_service_token: str = Header(...)
):
    verify_service_token(x_service_token)
    sql = """
        SELECT s.session_token_hash, s.user_id, s.csrf_token_hash, s.expires_at,
               u.email, u.full_name, u.is_active
        FROM FINSIGHT.USER_SESSIONS s
        JOIN FINSIGHT.USERS u ON s.user_id = u.user_id
        WHERE s.session_token_hash = ? AND s.expires_at > CURRENT TIMESTAMP AND u.is_active = 1
    """
    rows = db_manager.execute_query(sql, (session_token_hash,))
    if not rows:
        raise HTTPException(status_code=401, detail="Session invalid or expired")

    sess = rows[0]
    # Update last_active_at
    update_sql = "UPDATE FINSIGHT.USER_SESSIONS SET last_active_at = CURRENT TIMESTAMP WHERE session_token_hash = ?"
    db_manager.execute_statement(update_sql, (session_token_hash,))

    return {
        "session_token_hash": sess["session_token_hash"].strip(),
        "user_id": sess["user_id"].strip(),
        "csrf_token_hash": sess["csrf_token_hash"].strip(),
        "email": sess["email"].strip(),
        "full_name": sess["full_name"].strip(),
        "expires_at": str(sess["expires_at"])
    }

@router.delete("/sessions/{session_token_hash}")
def delete_session(
    session_token_hash: str,
    x_service_token: str = Header(...)
):
    verify_service_token(x_service_token)
    delete_sql = "DELETE FROM FINSIGHT.USER_SESSIONS WHERE session_token_hash = ?"
    db_manager.execute_statement(delete_sql, (session_token_hash,))
    return {"deleted": True}

@router.put("/sessions/{session_token_hash}/csrf")
def update_session_csrf(
    session_token_hash: str,
    req: UpdateCsrfRequest,
    x_service_token: str = Header(...)
):
    verify_service_token(x_service_token)
    update_sql = """
        UPDATE FINSIGHT.USER_SESSIONS
        SET csrf_token_hash = ?, last_active_at = CURRENT TIMESTAMP
        WHERE session_token_hash = ? AND expires_at > CURRENT TIMESTAMP
    """
    affected = db_manager.execute_statement(update_sql, (req.csrf_token_hash.strip(), session_token_hash.strip()))
    if affected == 0:
        raise HTTPException(status_code=401, detail="Session invalid or expired")
    return {"updated": True}

@router.get("/dashboard/summary")
def get_dashboard_summary(
    user_id: str = Query(...),
    x_service_token: str = Header(...)
):
    verify_service_token(x_service_token)
    # 1. Total income (CREDIT)
    inc_sql = """
        SELECT COALESCE(SUM(amount), 0.00)
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ? AND transaction_type = 'CREDIT' AND transaction_status = 'POSTED'
    """
    inc_rows = db_manager.execute_query(inc_sql, (user_id,))
    total_income = float(list(inc_rows[0].values())[0]) if inc_rows else 0.0

    # 2. Total expenses (DEBIT excluding internal transfers)
    exp_sql = """
        SELECT COALESCE(SUM(amount), 0.00)
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ? AND transaction_type = 'DEBIT' AND transaction_status = 'POSTED'
          AND (category_id IS NULL OR category_id != 'cat_transfer')
    """
    exp_rows = db_manager.execute_query(exp_sql, (user_id,))
    total_expenses = float(list(exp_rows[0].values())[0]) if exp_rows else 0.0

    net_savings = total_income - total_expenses

    # 3. Tx counts (posted, pending, total)
    cnt_sql = """
        SELECT
            COUNT(*) AS total_cnt,
            COALESCE(SUM(CASE WHEN transaction_status = 'POSTED' THEN 1 ELSE 0 END), 0) AS posted_cnt,
            COALESCE(SUM(CASE WHEN transaction_status = 'PENDING' THEN 1 ELSE 0 END), 0) AS pending_cnt
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ?
    """
    cnt_rows = db_manager.execute_query(cnt_sql, (user_id,))
    tx_count = int(cnt_rows[0]["total_cnt"]) if cnt_rows else 0
    posted_count = int(cnt_rows[0]["posted_cnt"]) if cnt_rows else 0
    pending_count = int(cnt_rows[0]["pending_cnt"]) if cnt_rows else 0

    # 4. Top spending categories
    cat_sql = """
        SELECT COALESCE(c.category_name, 'Uncategorized') AS category_name,
               SUM(t.amount) AS total_spent,
               COUNT(*) AS tx_count
        FROM FINSIGHT.TRANSACTIONS t
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE t.user_id = ? AND t.transaction_type = 'DEBIT'
          AND (t.category_id IS NULL OR t.category_id != 'cat_transfer')
        GROUP BY c.category_name
        ORDER BY total_spent DESC
        FETCH FIRST 6 ROWS ONLY
    """
    cat_rows = db_manager.execute_query(cat_sql, (user_id,))
    categories = [
        {
            "category": r["category_name"].strip(),
            "total_spent": float(r["total_spent"]),
            "count": int(r["tx_count"])
        }
        for r in cat_rows
    ]

    # 5. Anomalies count
    anom_sql = "SELECT COUNT(*) FROM FINSIGHT.ANOMALY_ALERTS WHERE user_id = ? AND status = 'NEW'"
    anom_rows = db_manager.execute_query(anom_sql, (user_id,))
    pending_anomalies = int(list(anom_rows[0].values())[0]) if anom_rows else 0

    # 6. Monthly trends (Income vs Expenses by month)
    month_sql = """
        SELECT
            VARCHAR_FORMAT(transaction_date, 'YYYY-MM') AS month_year,
            COALESCE(SUM(CASE WHEN transaction_type = 'CREDIT' AND transaction_status = 'POSTED' THEN amount ELSE 0.00 END), 0.00) AS income,
            COALESCE(SUM(CASE WHEN transaction_type = 'DEBIT' AND transaction_status = 'POSTED' AND (category_id IS NULL OR category_id != 'cat_transfer') THEN amount ELSE 0.00 END), 0.00) AS expenses
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ?
        GROUP BY VARCHAR_FORMAT(transaction_date, 'YYYY-MM')
        ORDER BY month_year ASC
    """
    month_rows = db_manager.execute_query(month_sql, (user_id,))
    monthly_trends = [
        {
            "month": r["month_year"].strip(),
            "income": float(r["income"]),
            "expenses": float(r["expenses"]),
            "net": float(r["income"]) - float(r["expenses"])
        }
        for r in month_rows
    ]

    return {
        "user_id": user_id,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_savings": net_savings,
        "total_transactions": tx_count,
        "posted_transactions": posted_count,
        "pending_transactions": pending_count,
        "pending_anomalies": pending_anomalies,
        "top_categories": categories,
        "monthly_trends": monthly_trends,
        "currency": "INR"
    }

@router.get("/transactions")
def get_transactions(
    user_id: str = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    category: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    x_service_token: str = Header(...)
):
    verify_service_token(x_service_token)
    where_clauses = ["t.user_id = ?"]
    params: List[Any] = [user_id]

    if category and category.strip():
        cat_val = category.strip()
        where_clauses.append("(LOWER(c.category_name) = LOWER(?) OR LOWER(t.category_id) = LOWER(?))")
        params.extend([cat_val, cat_val])

    if search and search.strip():
        like_pattern = f"%{search.strip().lower()}%"
        where_clauses.append(
            "(LOWER(t.merchant) LIKE ? OR LOWER(COALESCE(t.description, '')) LIKE ? OR LOWER(COALESCE(c.category_name, '')) LIKE ?)"
        )
        params.extend([like_pattern, like_pattern, like_pattern])

    where_sql = " AND ".join(where_clauses)

    # 1. Total matching count across complete dataset
    count_sql = f"""
        SELECT COUNT(*) AS total_count
        FROM FINSIGHT.TRANSACTIONS t
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE {where_sql}
    """
    count_rows = db_manager.execute_query(count_sql, tuple(params))
    total_count = int(list(count_rows[0].values())[0]) if count_rows else 0

    # 2. Paginated data slice
    data_sql = f"""
        SELECT t.transaction_id, t.user_id, t.account_id, t.category_id,
               t.merchant, t.description, t.amount, t.currency,
               t.transaction_type, t.transaction_date, t.transaction_status,
               COALESCE(c.category_name, 'Uncategorized') as category_name
        FROM FINSIGHT.TRANSACTIONS t
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE {where_sql}
        ORDER BY t.transaction_date DESC, t.transaction_id DESC
        OFFSET ? ROWS FETCH FIRST ? ROWS ONLY
    """
    rows = db_manager.execute_query(data_sql, tuple(params + [offset, limit]))

    txs = []
    for r in rows:
        txs.append({
            "transaction_id": r["transaction_id"].strip(),
            "user_id": r["user_id"].strip(),
            "account_id": r["account_id"].strip(),
            "category_id": r["category_id"].strip() if r["category_id"] else None,
            "category_name": r["category_name"].strip(),
            "merchant": r["merchant"].strip(),
            "description": r["description"].strip() if r["description"] else None,
            "amount": float(r["amount"]),
            "currency": r["currency"].strip(),
            "transaction_type": r["transaction_type"].strip(),
            "transaction_date": str(r["transaction_date"]),
            "status": r["transaction_status"].strip()
        })

    return {
        "user_id": user_id,
        "count": len(txs),
        "total_count": total_count,
        "offset": offset,
        "limit": limit,
        "transactions": txs
    }
