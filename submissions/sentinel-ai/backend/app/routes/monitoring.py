from typing import Optional, List
from fastapi import APIRouter, Query
from app.database.db2_connector import db_connector

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

@router.get("/users")
def get_users():
    return db_connector.execute_query("SELECT * FROM USER_ACCOUNTS ORDER BY full_name ASC")

@router.get("/logins")
def get_logins(user_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50):
    query = "SELECT l.*, u.full_name, u.email, u.department FROM LOGIN_EVENTS l LEFT JOIN USER_ACCOUNTS u ON l.user_id = u.user_id WHERE 1=1"
    params = []
    if user_id:
        query += " AND l.user_id = ?"
        params.append(user_id)
    if status:
        query += " AND l.status = ?"
        params.append(status.upper())
    query += " ORDER BY l.timestamp DESC LIMIT ?"
    params.append(limit)
    return db_connector.execute_query(query, tuple(params))

@router.get("/access-logs")
def get_access_logs(user_id: Optional[str] = None, classification: Optional[str] = None, limit: int = 50):
    query = "SELECT a.*, u.full_name, u.email, u.security_clearance FROM ACCESS_LOGS a LEFT JOIN USER_ACCOUNTS u ON a.user_id = u.user_id WHERE 1=1"
    params = []
    if user_id:
        query += " AND a.user_id = ?"
        params.append(user_id)
    if classification:
        query += " AND a.classification_level = ?"
        params.append(classification.upper())
    query += " ORDER BY a.timestamp DESC LIMIT ?"
    params.append(limit)
    return db_connector.execute_query(query, tuple(params))

@router.get("/alerts")
def get_alerts(user_id: Optional[str] = None, severity: Optional[str] = None, limit: int = 50):
    query = "SELECT al.*, u.full_name, u.email FROM SECURITY_ALERTS al LEFT JOIN USER_ACCOUNTS u ON al.user_id = u.user_id WHERE 1=1"
    params = []
    if user_id:
        query += " AND al.user_id = ?"
        params.append(user_id)
    if severity:
        query += " AND al.severity = ?"
        params.append(severity.upper())
    query += " ORDER BY al.timestamp DESC LIMIT ?"
    params.append(limit)
    return db_connector.execute_query(query, tuple(params))

