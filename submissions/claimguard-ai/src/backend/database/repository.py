"""
ClaimGuard AI - Enterprise Repository Layer
Implements parameterized SQL CRUD operations across all 7 IBM Db2 tables:
CUSTOMER_DETAILS, POLICY_DETAILS, CLAIM_RECORDS, DOCUMENT_RECORDS,
FRAUD_ALERTS, VERIFICATION_LOGS, and USERS.
"""

import json
import logging
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from ..config import settings
from .connection import db2_manager

logger = logging.getLogger("claimguard.repository")


class ClaimGuardRepository:
    """Repository handling all 7 tables with parameterized SQL and explicit demo fallback."""

    def __init__(self):
        # In-memory store for explicitly labelled demo fallback if Db2 instance is offline
        self._demo_customers: Dict[str, Dict[str, Any]] = {}
        self._demo_policies: Dict[str, Dict[str, Any]] = {}
        self._demo_claims: Dict[str, Dict[str, Any]] = {}
        self._demo_documents: Dict[str, Dict[str, Any]] = {}
        self._demo_alerts: Dict[str, Dict[str, Any]] = {}
        self._demo_logs: Dict[str, Dict[str, Any]] = {}
        self._demo_users: Dict[str, Dict[str, Any]] = {}
        self._init_demo_seeds()

    def _init_demo_seeds(self):
        """Initializes mock records matching schema.sql exactly."""
        self._demo_customers = {
            "CUST-001": {
                "CUSTOMER_ID": "CUST-001",
                "FIRST_NAME": "Aarav",
                "LAST_NAME": "Sharma",
                "EMAIL": "aarav.sharma@example.com",
                "PHONE": "+91 9876543210",
                "DATE_OF_BIRTH": "1988-04-12",
                "NATIONAL_ID": "IN-AADHAAR-9081",
                "ADDRESS": "74 Park View, Lucknow, UP",
                "CREATED_AT": "2026-01-10 10:00:00"
            },
            "CUST-002": {
                "CUSTOMER_ID": "CUST-002",
                "FIRST_NAME": "Priya",
                "LAST_NAME": "Verma",
                "EMAIL": "priya.verma@example.com",
                "PHONE": "+91 9811223344",
                "DATE_OF_BIRTH": "1992-09-24",
                "NATIONAL_ID": "IN-AADHAAR-6543",
                "ADDRESS": "12 Lake Street, Mathura, UP",
                "CREATED_AT": "2026-01-15 11:30:00"
            }
        }
        self._demo_policies = {
            "POL-1001": {
                "POLICY_ID": "POL-1001",
                "CUSTOMER_ID": "CUST-001",
                "POLICY_NUMBER": "POL-MED-2026-001",
                "POLICY_TYPE": "HEALTH_COMPREHENSIVE",
                "STATUS": "ACTIVE",
                "START_DATE": "2026-01-01",
                "END_DATE": "2026-12-31",
                "MAX_COVERAGE_AMOUNT": 500000.00,
                "REMAINING_COVERAGE": 420000.00,
                "DEDUCTIBLE": 5000.00,
                "COPAY_PERCENTAGE": 10.00,
                "CREATED_AT": "2026-01-01 00:00:00"
            },
            "POL-1002": {
                "POLICY_ID": "POL-1002",
                "CUSTOMER_ID": "CUST-002",
                "POLICY_NUMBER": "POL-MED-2026-002",
                "POLICY_TYPE": "CRITICAL_ILLNESS",
                "STATUS": "ACTIVE",
                "START_DATE": "2026-02-15",
                "END_DATE": "2027-02-14",
                "MAX_COVERAGE_AMOUNT": 1000000.00,
                "REMAINING_COVERAGE": 1000000.00,
                "DEDUCTIBLE": 10000.00,
                "COPAY_PERCENTAGE": 5.00,
                "CREATED_AT": "2026-02-15 00:00:00"
            }
        }
        self._demo_claims = {
            "CLM-9001": {
                "CLAIM_ID": "CLM-9001",
                "POLICY_ID": "POL-1001",
                "CUSTOMER_ID": "CUST-001",
                "CLAIM_NUMBER": "CLM-2026-001",
                "INCIDENT_DATE": "2026-10-12",
                "ADMISSION_DATE": "2026-10-12",
                "DISCHARGE_DATE": "2026-10-15",
                "CLAIM_AMOUNT": 80000.00,
                "APPROVED_AMOUNT": 80000.00,
                "HOSPITAL_NAME": "Apollo Hospital Lucknow",
                "HOSPITAL_INVOICE_NUMBER": "INV-APL-2026-8812",
                "DIAGNOSIS_CODE": "A09",
                "DIAGNOSIS_DESCRIPTION": "Acute gastroenteritis with mild dehydration",
                "STATUS": "APPROVED",
                "RISK_SCORE": 12.50,
                "RISK_LEVEL": "LOW",
                "DECISION_NOTES": "Documents verified and coverage confirmed.",
                "REVIEWED_BY": "USR-001",
                "SUBMITTED_AT": "2026-10-16 09:15:00",
                "UPDATED_AT": "2026-10-16 11:30:00"
            }
        }
        self._demo_users = {
            "examiner": {
                "USER_ID": "USR-001",
                "USERNAME": "examiner",
                "EMAIL": "examiner@claimguard.ibm",
                "HASHED_PASSWORD": "pbkdf2:sha256:600000$f0bbc5600354028e5f1dcdc828b724bf$07d10841141db70e0af48b07275f28ff153ba72dd2d522a94e20d07bab62365f",
                "FULL_NAME": "Dhruv Senior Examiner",
                "ROLE": "REVIEWER",
                "IS_ACTIVE": 1,
                "CREATED_AT": "2026-01-01 00:00:00"
            },
            "admin": {
                "USER_ID": "USR-002",
                "USERNAME": "admin",
                "EMAIL": "admin@claimguard.ibm",
                "HASHED_PASSWORD": "pbkdf2:sha256:600000$af483c3b6ae8b412b8b933c43c550d54$2988a2bbb01880316f9bb7d3306a77025358d640cd67b64d61d1a9e7bde0f79d",
                "FULL_NAME": "Nitesh Administrator",
                "ROLE": "ADMIN",
                "IS_ACTIVE": 1,
                "CREATED_AT": "2026-01-01 00:00:00"
            }
        }

    # --------------------------------------------------------------------------
    # 1. CUSTOMER_DETAILS OPERATIONS
    # --------------------------------------------------------------------------
    def get_customer_by_id(self, customer_id: str) -> Optional[Dict[str, Any]]:
        conn = db2_manager.get_connection()
        if conn:
            sql = "SELECT * FROM CUSTOMER_DETAILS WHERE CUSTOMER_ID = ?"
            res = db2_manager.execute_query(sql, (customer_id,))
            return res[0] if res else None

        if settings.DEMO_MODE:
            cust = self._demo_customers.get(customer_id)
            return dict(cust) if cust else None
        return None

    def list_customers(self) -> List[Dict[str, Any]]:
        conn = db2_manager.get_connection()
        if conn:
            sql = "SELECT * FROM CUSTOMER_DETAILS ORDER BY CREATED_AT DESC"
            return db2_manager.execute_query(sql)

        if settings.DEMO_MODE:
            return list(self._demo_customers.values())
        return []

    def create_customer(self, customer: Dict[str, Any]) -> Dict[str, Any]:
        cust_id = customer.get("CUSTOMER_ID") or f"CUST-{uuid.uuid4().hex[:6].upper()}"
        customer["CUSTOMER_ID"] = cust_id
        customer["CREATED_AT"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = db2_manager.get_connection()
        if conn:
            sql = """
                INSERT INTO CUSTOMER_DETAILS 
                (CUSTOMER_ID, FIRST_NAME, LAST_NAME, EMAIL, PHONE, DATE_OF_BIRTH, NATIONAL_ID, ADDRESS)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                cust_id,
                customer.get("FIRST_NAME"),
                customer.get("LAST_NAME"),
                customer.get("EMAIL"),
                customer.get("PHONE"),
                customer.get("DATE_OF_BIRTH"),
                customer.get("NATIONAL_ID"),
                customer.get("ADDRESS")
            )
            db2_manager.execute_statement(sql, params)
            return customer

        if settings.DEMO_MODE:
            self._demo_customers[cust_id] = customer
            return customer
        raise ConnectionError("IBM Db2 is unavailable.")

    # --------------------------------------------------------------------------
    # 2. POLICY_DETAILS OPERATIONS
    # --------------------------------------------------------------------------
    def get_policy_by_id(self, policy_id: str) -> Optional[Dict[str, Any]]:
        conn = db2_manager.get_connection()
        if conn:
            sql = "SELECT * FROM POLICY_DETAILS WHERE POLICY_ID = ?"
            res = db2_manager.execute_query(sql, (policy_id,))
            return res[0] if res else None

        if settings.DEMO_MODE:
            pol = self._demo_policies.get(policy_id)
            return dict(pol) if pol else None
        return None

    def get_policy_by_number(self, policy_number: str) -> Optional[Dict[str, Any]]:
        conn = db2_manager.get_connection()
        if conn:
            sql = "SELECT * FROM POLICY_DETAILS WHERE POLICY_NUMBER = ?"
            res = db2_manager.execute_query(sql, (policy_number,))
            return res[0] if res else None

        if settings.DEMO_MODE:
            for pol in self._demo_policies.values():
                if pol.get("POLICY_NUMBER") == policy_number:
                    return dict(pol)
            return None
        return None

    def list_policies(self) -> List[Dict[str, Any]]:
        conn = db2_manager.get_connection()
        if conn:
            sql = "SELECT * FROM POLICY_DETAILS ORDER BY CREATED_AT DESC"
            return db2_manager.execute_query(sql)

        if settings.DEMO_MODE:
            return list(self._demo_policies.values())
        return []

    def update_policy_coverage(self, policy_id: str, new_remaining: float) -> bool:
        conn = db2_manager.get_connection()
        if conn:
            sql = "UPDATE POLICY_DETAILS SET REMAINING_COVERAGE = ? WHERE POLICY_ID = ?"
            affected = db2_manager.execute_statement(sql, (Decimal(str(new_remaining)), policy_id))
            return affected > 0

        if settings.DEMO_MODE and policy_id in self._demo_policies:
            self._demo_policies[policy_id]["REMAINING_COVERAGE"] = float(new_remaining)
            return True
        return False

    # --------------------------------------------------------------------------
    # 3. CLAIM_RECORDS OPERATIONS
    # --------------------------------------------------------------------------
    def create_claim(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        claim_id = claim.get("CLAIM_ID") or f"CLM-{uuid.uuid4().hex[:6].upper()}"
        claim_number = claim.get("CLAIM_NUMBER") or f"CLM-2026-{uuid.uuid4().hex[:4].upper()}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        claim["CLAIM_ID"] = claim_id
        claim["CLAIM_NUMBER"] = claim_number
        claim.setdefault("STATUS", "PENDING")
        claim.setdefault("RISK_SCORE", 0.0)
        claim.setdefault("RISK_LEVEL", "LOW")
        claim.setdefault("SUBMITTED_AT", now_str)
        claim.setdefault("UPDATED_AT", now_str)

        conn = db2_manager.get_connection()
        if conn:
            try:
                db2_manager.execute_statement("DELETE FROM CLAIM_RECORDS WHERE CLAIM_ID = ?", (claim_id,))
            except Exception:
                pass
            sql = """
                INSERT INTO CLAIM_RECORDS 
                (CLAIM_ID, POLICY_ID, CUSTOMER_ID, CLAIM_NUMBER, INCIDENT_DATE, ADMISSION_DATE, DISCHARGE_DATE, 
                 CLAIM_AMOUNT, APPROVED_AMOUNT, HOSPITAL_NAME, HOSPITAL_INVOICE_NUMBER, DIAGNOSIS_CODE, 
                 DIAGNOSIS_DESCRIPTION, STATUS, RISK_SCORE, RISK_LEVEL, DECISION_NOTES, REVIEWED_BY, 
                 SUBMITTED_AT, UPDATED_AT)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                claim_id,
                claim["POLICY_ID"],
                claim["CUSTOMER_ID"],
                claim_number,
                claim.get("INCIDENT_DATE"),
                claim.get("ADMISSION_DATE"),
                claim.get("DISCHARGE_DATE"),
                Decimal(str(claim.get("CLAIM_AMOUNT", 0))),
                Decimal(str(claim.get("APPROVED_AMOUNT", 0))),
                claim.get("HOSPITAL_NAME"),
                claim.get("HOSPITAL_INVOICE_NUMBER"),
                claim.get("DIAGNOSIS_CODE"),
                claim.get("DIAGNOSIS_DESCRIPTION"),
                claim.get("STATUS", "PENDING"),
                Decimal(str(claim.get("RISK_SCORE", 0))),
                claim.get("RISK_LEVEL", "LOW"),
                claim.get("DECISION_NOTES"),
                claim.get("REVIEWED_BY"),
                now_str,
                now_str
            )
            db2_manager.execute_statement(sql, params)
            return claim

        if settings.DEMO_MODE:
            self._demo_claims[claim_id] = claim
            return claim
        raise ConnectionError("IBM Db2 is unavailable.")

    def get_claim_by_id(self, claim_id: str) -> Optional[Dict[str, Any]]:
        conn = db2_manager.get_connection()
        if conn:
            sql = "SELECT * FROM CLAIM_RECORDS WHERE CLAIM_ID = ?"
            res = db2_manager.execute_query(sql, (claim_id,))
            return res[0] if res else None

        if settings.DEMO_MODE:
            clm = self._demo_claims.get(claim_id)
            return dict(clm) if clm else None
        return None

    def list_claims(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = db2_manager.get_connection()
        if conn:
            if status:
                sql = "SELECT * FROM CLAIM_RECORDS WHERE STATUS = ? ORDER BY SUBMITTED_AT DESC"
                return db2_manager.execute_query(sql, (status,))
            else:
                sql = "SELECT * FROM CLAIM_RECORDS ORDER BY SUBMITTED_AT DESC"
                return db2_manager.execute_query(sql)

        if settings.DEMO_MODE:
            results = list(self._demo_claims.values())
            if status:
                results = [c for c in results if c.get("STATUS") == status]
            return sorted(results, key=lambda x: str(x.get("SUBMITTED_AT", "")), reverse=True)
        return []

    def update_claim_risk(self, claim_id: str, risk_score: float, risk_level: str) -> bool:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = db2_manager.get_connection()
        if conn:
            sql = "UPDATE CLAIM_RECORDS SET RISK_SCORE = ?, RISK_LEVEL = ?, UPDATED_AT = ? WHERE CLAIM_ID = ?"
            affected = db2_manager.execute_statement(
                sql, (Decimal(str(risk_score)), risk_level, now_str, claim_id)
            )
            return affected > 0

        if settings.DEMO_MODE and claim_id in self._demo_claims:
            self._demo_claims[claim_id]["RISK_SCORE"] = float(risk_score)
            self._demo_claims[claim_id]["RISK_LEVEL"] = risk_level
            self._demo_claims[claim_id]["UPDATED_AT"] = now_str
            return True
        return False

    def update_claim_decision(
        self,
        claim_id: str,
        status: str,
        decision_notes: Optional[str] = None,
        reviewed_by: Optional[str] = None,
        approved_amount: Optional[float] = None
    ) -> bool:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = db2_manager.get_connection()
        if conn:
            sql = """
                UPDATE CLAIM_RECORDS 
                SET STATUS = ?, DECISION_NOTES = ?, REVIEWED_BY = ?, 
                    APPROVED_AMOUNT = ?, UPDATED_AT = ?
                WHERE CLAIM_ID = ?
            """
            params = (
                status,
                decision_notes,
                reviewed_by,
                Decimal(str(approved_amount or 0)),
                now_str,
                claim_id
            )
            affected = db2_manager.execute_statement(sql, params)
            return affected > 0

        if settings.DEMO_MODE and claim_id in self._demo_claims:
            self._demo_claims[claim_id]["STATUS"] = status
            self._demo_claims[claim_id]["DECISION_NOTES"] = decision_notes
            self._demo_claims[claim_id]["REVIEWED_BY"] = reviewed_by
            if approved_amount is not None:
                self._demo_claims[claim_id]["APPROVED_AMOUNT"] = float(approved_amount)
            self._demo_claims[claim_id]["UPDATED_AT"] = now_str
            return True
        return False

    def find_claims_by_invoice(self, invoice_num: str, exclude_claim_id: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = db2_manager.get_connection()
        if conn:
            if exclude_claim_id:
                sql = "SELECT * FROM CLAIM_RECORDS WHERE HOSPITAL_INVOICE_NUMBER = ? AND CLAIM_ID != ?"
                return db2_manager.execute_query(sql, (invoice_num, exclude_claim_id))
            sql = "SELECT * FROM CLAIM_RECORDS WHERE HOSPITAL_INVOICE_NUMBER = ?"
            return db2_manager.execute_query(sql, (invoice_num,))

        if settings.DEMO_MODE:
            matches = [
                c for c in self._demo_claims.values()
                if c.get("HOSPITAL_INVOICE_NUMBER") == invoice_num
                and (not exclude_claim_id or c.get("CLAIM_ID") != exclude_claim_id)
            ]
            return matches
        return []

    # --------------------------------------------------------------------------
    # 4. DOCUMENT_RECORDS OPERATIONS
    # --------------------------------------------------------------------------
    def create_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        doc_id = doc.get("DOCUMENT_ID") or f"DOC-{uuid.uuid4().hex[:6].upper()}"
        doc["DOCUMENT_ID"] = doc_id
        doc["UPLOADED_AT"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = db2_manager.get_connection()
        if conn:
            try:
                db2_manager.execute_statement("DELETE FROM DOCUMENT_RECORDS WHERE DOCUMENT_ID = ?", (doc_id,))
            except Exception:
                pass
            sql = """
                INSERT INTO DOCUMENT_RECORDS 
                (DOCUMENT_ID, CLAIM_ID, DOCUMENT_NAME, DOCUMENT_TYPE, FILE_PATH, FILE_HASH, 
                 FILE_SIZE_BYTES, MIME_TYPE, EXTRACTED_DATA, UPLOADED_AT)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                doc_id,
                doc["CLAIM_ID"],
                doc["DOCUMENT_NAME"],
                doc["DOCUMENT_TYPE"],
                doc["FILE_PATH"],
                doc["FILE_HASH"],
                int(doc.get("FILE_SIZE_BYTES", 0)),
                doc["MIME_TYPE"],
                doc.get("EXTRACTED_DATA"),
                doc["UPLOADED_AT"]
            )
            db2_manager.execute_statement(sql, params)
            return doc

        if settings.DEMO_MODE:
            self._demo_documents[doc_id] = doc
            return doc
        raise ConnectionError("IBM Db2 is unavailable.")

    def find_documents_by_hash(self, file_hash: str, exclude_claim_id: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = db2_manager.get_connection()
        if conn:
            if exclude_claim_id:
                sql = "SELECT * FROM DOCUMENT_RECORDS WHERE FILE_HASH = ? AND CLAIM_ID != ?"
                return db2_manager.execute_query(sql, (file_hash, exclude_claim_id))
            sql = "SELECT * FROM DOCUMENT_RECORDS WHERE FILE_HASH = ?"
            return db2_manager.execute_query(sql, (file_hash,))

        if settings.DEMO_MODE:
            matches = [
                d for d in self._demo_documents.values()
                if d.get("FILE_HASH") == file_hash
                and (not exclude_claim_id or d.get("CLAIM_ID") != exclude_claim_id)
            ]
            return matches
        return []

    def get_documents_by_claim(self, claim_id: str) -> List[Dict[str, Any]]:
        conn = db2_manager.get_connection()
        if conn:
            sql = "SELECT * FROM DOCUMENT_RECORDS WHERE CLAIM_ID = ? ORDER BY UPLOADED_AT DESC"
            return db2_manager.execute_query(sql, (claim_id,))

        if settings.DEMO_MODE:
            return [d for d in self._demo_documents.values() if d.get("CLAIM_ID") == claim_id]
        return []

    # --------------------------------------------------------------------------
    # 5. FRAUD_ALERTS OPERATIONS
    # --------------------------------------------------------------------------
    def create_fraud_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        alert_id = alert.get("ALERT_ID") or f"ALT-{uuid.uuid4().hex[:6].upper()}"
        alert["ALERT_ID"] = alert_id
        alert["CREATED_AT"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alert.setdefault("IS_RESOLVED", 0)

        conn = db2_manager.get_connection()
        if conn:
            sql = """
                INSERT INTO FRAUD_ALERTS 
                (ALERT_ID, CLAIM_ID, ALERT_TYPE, SEVERITY, DESCRIPTION, EVIDENCE_DETAILS, 
                 IS_RESOLVED, RESOLVED_BY, RESOLUTION_NOTES, CREATED_AT)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                alert_id,
                alert["CLAIM_ID"],
                alert["ALERT_TYPE"],
                alert["SEVERITY"],
                alert["DESCRIPTION"],
                alert.get("EVIDENCE_DETAILS"),
                alert.get("IS_RESOLVED", 0),
                alert.get("RESOLVED_BY"),
                alert.get("RESOLUTION_NOTES"),
                alert["CREATED_AT"]
            )
            db2_manager.execute_statement(sql, params)
            return alert

        if settings.DEMO_MODE:
            self._demo_alerts[alert_id] = alert
            return alert
        raise ConnectionError("IBM Db2 is unavailable.")

    def get_alerts_by_claim(self, claim_id: str) -> List[Dict[str, Any]]:
        conn = db2_manager.get_connection()
        if conn:
            sql = "SELECT * FROM FRAUD_ALERTS WHERE CLAIM_ID = ? ORDER BY CREATED_AT DESC"
            return db2_manager.execute_query(sql, (claim_id,))

        if settings.DEMO_MODE:
            return [a for a in self._demo_alerts.values() if a.get("CLAIM_ID") == claim_id]
        return []

    def list_all_alerts(self, resolved: Optional[bool] = None) -> List[Dict[str, Any]]:
        conn = db2_manager.get_connection()
        if conn:
            if resolved is not None:
                val = 1 if resolved else 0
                sql = "SELECT * FROM FRAUD_ALERTS WHERE IS_RESOLVED = ? ORDER BY CREATED_AT DESC"
                return db2_manager.execute_query(sql, (val,))
            sql = "SELECT * FROM FRAUD_ALERTS ORDER BY CREATED_AT DESC"
            return db2_manager.execute_query(sql)

        if settings.DEMO_MODE:
            alerts = list(self._demo_alerts.values())
            if resolved is not None:
                val = 1 if resolved else 0
                alerts = [a for a in alerts if a.get("IS_RESOLVED") == val]
            return alerts
        return []

    def resolve_alert(self, alert_id: str, resolved_by: str, notes: str) -> bool:
        conn = db2_manager.get_connection()
        if conn:
            sql = "UPDATE FRAUD_ALERTS SET IS_RESOLVED = 1, RESOLVED_BY = ?, RESOLUTION_NOTES = ? WHERE ALERT_ID = ?"
            affected = db2_manager.execute_statement(sql, (resolved_by, notes, alert_id))
            return affected > 0

        if settings.DEMO_MODE and alert_id in self._demo_alerts:
            self._demo_alerts[alert_id]["IS_RESOLVED"] = 1
            self._demo_alerts[alert_id]["RESOLVED_BY"] = resolved_by
            self._demo_alerts[alert_id]["RESOLUTION_NOTES"] = notes
            return True
        return False

    # --------------------------------------------------------------------------
    # 6. VERIFICATION_LOGS OPERATIONS
    # --------------------------------------------------------------------------
    def create_log(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        log_id = log_entry.get("LOG_ID") or f"LOG-{uuid.uuid4().hex[:6].upper()}"
        log_entry["LOG_ID"] = log_id
        log_entry["CREATED_AT"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = db2_manager.get_connection()
        if conn:
            sql = """
                INSERT INTO VERIFICATION_LOGS 
                (LOG_ID, CLAIM_ID, AGENT_NAME, ACTION, STATUS, DETAILS, EXECUTION_TIME_MS, CREATED_AT)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                log_id,
                log_entry["CLAIM_ID"],
                log_entry["AGENT_NAME"],
                log_entry["ACTION"],
                log_entry["STATUS"],
                log_entry.get("DETAILS"),
                log_entry.get("EXECUTION_TIME_MS", 0),
                log_entry["CREATED_AT"]
            )
            db2_manager.execute_statement(sql, params)
            return log_entry

        if settings.DEMO_MODE:
            self._demo_logs[log_id] = log_entry
            return log_entry
        raise ConnectionError("IBM Db2 is unavailable.")

    def get_logs_by_claim(self, claim_id: str) -> List[Dict[str, Any]]:
        conn = db2_manager.get_connection()
        if conn:
            sql = "SELECT * FROM VERIFICATION_LOGS WHERE CLAIM_ID = ? ORDER BY CREATED_AT ASC"
            return db2_manager.execute_query(sql, (claim_id,))

        if settings.DEMO_MODE:
            logs = [l for l in self._demo_logs.values() if l.get("CLAIM_ID") == claim_id]
            return sorted(logs, key=lambda x: str(x.get("CREATED_AT", "")))
        return []

    def list_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = db2_manager.get_connection()
        if conn:
            sql = f"SELECT * FROM VERIFICATION_LOGS ORDER BY CREATED_AT DESC FETCH FIRST {limit} ROWS ONLY"
            return db2_manager.execute_query(sql)

        if settings.DEMO_MODE:
            logs = sorted(self._demo_logs.values(), key=lambda x: str(x.get("CREATED_AT", "")), reverse=True)
            return logs[:limit]
        return []

    # --------------------------------------------------------------------------
    # 7. USERS OPERATIONS
    # --------------------------------------------------------------------------
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        conn = db2_manager.get_connection()
        if conn:
            sql = "SELECT * FROM USERS WHERE USERNAME = ?"
            res = db2_manager.execute_query(sql, (username,))
            return res[0] if res else None

        if settings.DEMO_MODE:
            user = self._demo_users.get(username)
            return dict(user) if user else None
        return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        conn = db2_manager.get_connection()
        if conn:
            sql = "SELECT * FROM USERS WHERE USER_ID = ?"
            res = db2_manager.execute_query(sql, (user_id,))
            return res[0] if res else None

        if settings.DEMO_MODE:
            for u in self._demo_users.values():
                if u.get("USER_ID") == user_id:
                    return dict(u)
            return None
        return None


repository = ClaimGuardRepository()
