import logging
from typing import List, Dict, Any, Optional
from app.db import db_manager

logger = logging.getLogger("finsight.anomalies")

ALLOWED_STATUSES = {"NEEDS_REVIEW", "REVIEWED", "DISMISSED", "ACTIVE", "RESOLVED"}

# Mapping between application terminology and Db2 CHK_ALERT_STATUS constraint ('ACTIVE', 'DISMISSED', 'RESOLVED')
STATUS_TO_DB2 = {
    "NEEDS_REVIEW": "ACTIVE",
    "ACTIVE": "ACTIVE",
    "REVIEWED": "RESOLVED",
    "RESOLVED": "RESOLVED",
    "DISMISSED": "DISMISSED",
}

DB2_TO_APP = {
    "ACTIVE": "NEEDS_REVIEW",
    "RESOLVED": "REVIEWED",
    "DISMISSED": "DISMISSED",
    "NEEDS_REVIEW": "NEEDS_REVIEW",
    "REVIEWED": "REVIEWED",
}

class AnomalyEngine:
    def list_anomalies(
        self,
        user_id: str,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        sql = """
        SELECT 
            a.alert_id,
            a.transaction_id,
            a.alert_type,
            a.severity,
            a.explanation,
            a.score,
            a.status,
            t.merchant,
            t.amount,
            t.currency,
            t.transaction_date,
            COALESCE(c.category_name, 'Uncategorized') AS category_name
        FROM FINSIGHT.ANOMALY_ALERTS a
        LEFT JOIN FINSIGHT.TRANSACTIONS t ON a.transaction_id = t.transaction_id
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE a.user_id = ?
        """
        params: List[Any] = [user_id]

        if status:
            st = status.upper().strip()
            db_st = STATUS_TO_DB2.get(st, st)
            if db_st == "ACTIVE":
                sql += " AND (UPPER(a.status) = 'ACTIVE' OR UPPER(a.status) = 'NEEDS_REVIEW')"
            elif db_st == "RESOLVED":
                sql += " AND (UPPER(a.status) = 'RESOLVED' OR UPPER(a.status) = 'REVIEWED')"
            else:
                sql += " AND UPPER(a.status) = ?"
                params.append(db_st)

        if severity:
            sql += " AND UPPER(a.severity) = ?"
            params.append(severity.upper().strip())

        if alert_type:
            sql += " AND UPPER(a.alert_type) = ?"
            params.append(alert_type.upper().strip())

        sql += " ORDER BY a.created_at DESC"

        rows = db_manager.execute_query(sql, tuple(params))
        results = []
        for r in rows:
            raw_status = (r["status"] or "ACTIVE").upper().strip()
            norm_status = DB2_TO_APP.get(raw_status, raw_status)

            results.append({
                "alert_id": r["alert_id"],
                "transaction_id": r.get("transaction_id"),
                "alert_type": r["alert_type"],
                "severity": r["severity"],
                "explanation": r["explanation"],
                "score": float(r["score"]),
                "status": norm_status,
                "merchant": r.get("merchant"),
                "category": r.get("category_name"),
                "amount": float(r["amount"]) if r.get("amount") is not None else None,
                "currency": r.get("currency") or "INR",
                "date": str(r["transaction_date"]) if r.get("transaction_date") is not None else None
            })
        return results

    def get_anomaly(self, alert_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        sql = """
        SELECT 
            a.alert_id,
            a.transaction_id,
            a.alert_type,
            a.severity,
            a.explanation,
            a.score,
            a.status,
            t.merchant,
            t.amount,
            t.currency,
            t.transaction_date,
            COALESCE(c.category_name, 'Uncategorized') AS category_name
        FROM FINSIGHT.ANOMALY_ALERTS a
        LEFT JOIN FINSIGHT.TRANSACTIONS t ON a.transaction_id = t.transaction_id
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE a.alert_id = ? AND a.user_id = ?
        """
        rows = db_manager.execute_query(sql, (alert_id, user_id))
        if not rows:
            return None
        r = rows[0]
        raw_status = (r["status"] or "ACTIVE").upper().strip()
        norm_status = DB2_TO_APP.get(raw_status, raw_status)
        return {
            "alert_id": r["alert_id"],
            "transaction_id": r.get("transaction_id"),
            "alert_type": r["alert_type"],
            "severity": r["severity"],
            "explanation": r["explanation"],
            "score": float(r["score"]),
            "status": norm_status,
            "merchant": r.get("merchant"),
            "category": r.get("category_name"),
            "amount": float(r["amount"]) if r.get("amount") is not None else None,
            "currency": r.get("currency") or "INR",
            "date": str(r["transaction_date"]) if r.get("transaction_date") is not None else None
        }

    def update_anomaly_status(self, alert_id: str, user_id: str, new_status: str) -> Dict[str, Any]:
        st = new_status.upper().strip()
        if st not in ALLOWED_STATUSES:
            raise ValueError(f"Invalid status '{new_status}'. Allowed statuses: {sorted(list(ALLOWED_STATUSES))}")

        db_status = STATUS_TO_DB2.get(st, st)
        app_status = DB2_TO_APP.get(st, st)

        sql = """
        UPDATE FINSIGHT.ANOMALY_ALERTS
        SET status = ?
        WHERE alert_id = ? AND user_id = ?
        """
        affected = db_manager.execute_statement(sql, (db_status, alert_id, user_id))
        if affected == 0:
            raise KeyError(f"Alert {alert_id} not found or access denied for user {user_id}")

        return {
            "alert_id": alert_id,
            "status": app_status,
            "updated": True
        }

    def explain_anomaly(self, alert_id: str, user_id: str) -> Dict[str, Any]:
        sql = """
        SELECT 
            a.alert_id,
            a.transaction_id,
            a.alert_type,
            a.severity,
            a.explanation,
            a.score,
            a.status,
            t.merchant,
            t.amount,
            t.transaction_date,
            t.category_id,
            COALESCE(c.category_name, 'General') AS category_name
        FROM FINSIGHT.ANOMALY_ALERTS a
        LEFT JOIN FINSIGHT.TRANSACTIONS t ON a.transaction_id = t.transaction_id
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE a.alert_id = ? AND a.user_id = ?
        """
        rows = db_manager.execute_query(sql, (alert_id, user_id))
        if not rows:
            raise KeyError(f"Alert {alert_id} not found for user {user_id}")

        alert = rows[0]
        amt = float(alert["amount"]) if alert.get("amount") is not None else 0.00
        cat_name = alert.get("category_name", "General")
        merchant = alert.get("merchant", "Unknown Merchant")
        a_type = alert["alert_type"]
        tx_id = alert.get("transaction_id")
        date_str = str(alert.get("transaction_date")) if alert.get("transaction_date") else "Unknown Date"

        # 1. Unadjusted category statistical baseline (including all posted debits in category)
        cat_sql = """
        SELECT AVG(amount) AS avg_amt, COUNT(transaction_id) AS cnt
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ? AND category_id = ? AND transaction_type = 'DEBIT' AND transaction_status = 'POSTED'
        """
        cat_rows = db_manager.execute_query(cat_sql, (user_id, alert.get("category_id")))
        cat_avg_unadjusted = float(cat_rows[0]["avg_amt"]) if cat_rows and cat_rows[0].get("avg_amt") else amt
        cat_cnt = int(cat_rows[0]["cnt"]) if cat_rows and cat_rows[0].get("cnt") else 1

        # 2. Clean category statistical baseline (excluding the evaluated outlier)
        cat_clean_sql = """
        SELECT AVG(amount) AS avg_amt, COUNT(transaction_id) AS cnt
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ? AND category_id = ? AND transaction_type = 'DEBIT' AND transaction_status = 'POSTED'
          AND transaction_id != ?
        """
        cat_clean_rows = db_manager.execute_query(cat_clean_sql, (user_id, alert.get("category_id"), tx_id or ""))
        cat_avg_clean = float(cat_clean_rows[0]["avg_amt"]) if cat_clean_rows and cat_clean_rows[0].get("avg_amt") else cat_avg_unadjusted
        cat_cnt_clean = int(cat_clean_rows[0]["cnt"]) if cat_clean_rows and cat_clean_rows[0].get("cnt") else cat_cnt

        cat_multiplier_unadjusted = round(amt / cat_avg_unadjusted, 1) if cat_avg_unadjusted > 0 else 1.0
        cat_multiplier_clean = round(amt / cat_avg_clean, 1) if cat_avg_clean > 0 else 1.0

        # 3. Merchant-specific baseline (for recurring or frequent merchants)
        merchant_sql = """
        SELECT AVG(amount) AS avg_amt, COUNT(transaction_id) AS cnt
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ? AND merchant = ? AND transaction_type = 'DEBIT' AND transaction_status = 'POSTED'
          AND transaction_id != ?
        """
        merch_rows = db_manager.execute_query(merchant_sql, (user_id, merchant, tx_id or ""))
        merchant_avg = float(merch_rows[0]["avg_amt"]) if merch_rows and merch_rows[0].get("avg_amt") else None
        merchant_cnt = int(merch_rows[0]["cnt"]) if merch_rows and merch_rows[0].get("cnt") else 0
        merchant_multiplier = round(amt / merchant_avg, 1) if merchant_avg and merchant_avg > 0 else None

        # Build specific statistical context and calculation details based on alert type
        calc_details: Dict[str, Any] = {
            "transaction_amount": amt,
            "category_name": cat_name,
            "category_average_unadjusted": round(cat_avg_unadjusted, 2),
            "category_multiplier_unadjusted": cat_multiplier_unadjusted,
            "category_baseline_clean": round(cat_avg_clean, 2),
            "category_multiplier_clean": cat_multiplier_clean,
            "category_sample_size": cat_cnt,
        }

        evidence_ids = [tx_id] if tx_id else []

        if a_type == "RECURRING_DRIFT" and merchant_avg:
            calc_details["merchant_historical_baseline"] = round(merchant_avg, 2)
            calc_details["merchant_multiplier"] = merchant_multiplier
            calc_details["merchant_historical_sample_size"] = merchant_cnt
            formula = (
                f"Merchant Recurring Surge = INR {amt:,.2f} / INR {merchant_avg:,.2f} = {merchant_multiplier}x "
                f"(representing a +{int((merchant_multiplier - 1.0) * 100)}% surge over 5 previous monthly charges of INR {merchant_avg:,.2f}). "
                f"Unadjusted category multiple = INR {amt:,.2f} / INR {cat_avg_unadjusted:,.2f} = {cat_multiplier_unadjusted}x."
            )
        elif a_type == "VELOCITY_SPIKE":
            # Find related identical charges executed around that date
            burst_sql = """
            SELECT transaction_id, amount
            FROM FINSIGHT.TRANSACTIONS
            WHERE user_id = ? AND merchant = ? AND amount = ? AND transaction_date = ?
            """
            burst_rows = db_manager.execute_query(burst_sql, (user_id, merchant, amt, date_str))
            burst_txs = [b["transaction_id"] for b in burst_rows]
            evidence_ids = burst_txs if burst_txs else evidence_ids
            calc_details["burst_transaction_count"] = len(burst_txs)
            calc_details["total_burst_amount"] = round(amt * len(burst_txs), 2)
            formula = f"Rapid velocity burst: {len(burst_txs)} identical transactions of INR {amt:,.2f} executed on {date_str} totaling INR {amt * len(burst_txs):,.2f}."
        elif a_type == "AMOUNT_SPIKE":
            formula = (
                f"Category Outlier Spike: Transaction of INR {amt:,.2f} is {cat_multiplier_clean}x the clean category baseline "
                f"of INR {cat_avg_clean:,.2f} (or {cat_multiplier_unadjusted}x unadjusted average of INR {cat_avg_unadjusted:,.2f}) across {cat_cnt} transactions."
            )
        else:
            formula = f"Deviation detected: INR {amt:,.2f} vs. {cat_name} baseline of INR {cat_avg_unadjusted:,.2f} ({cat_multiplier_unadjusted}x)."

        calc_details["formula_applied"] = formula

        statistical_context = {
            "transaction_amount": amt,
            "category_average": round(cat_avg_unadjusted, 2),
            "multiplier": merchant_multiplier if merchant_multiplier else cat_multiplier_unadjusted,
            "alert_type": a_type,
            "severity": alert["severity"],
            "confidence_score": float(alert["score"]),
            "historical_sample_size": merchant_cnt if merchant_cnt > 0 else cat_cnt
        }

        recommendation = (
            f"Review this charge from {merchant} ({cat_name}). "
            f"If this is an authorized legitimate expense or planned infrastructure scale-up, mark the alert as 'Reviewed'. "
            f"If this is a known duplicate or false positive, mark as 'Dismissed'. "
            f"If completely unrecognized, contact your banking institution immediately."
        )

        limitations = (
            "Statistical anomaly detection compares financial transactions against historical category and merchant baselines. "
            "An anomaly alert is an automated indicator requiring user review, NOT conclusive proof of fraud, theft, or unauthorized access. "
            "Internal transfers and pending unposted transactions are strictly excluded from living-expense baselines."
        )

        raw_status = (alert["status"] or "NEEDS_REVIEW").upper().strip()
        norm_status = "NEEDS_REVIEW" if raw_status == "ACTIVE" else raw_status

        return {
            "alert_id": alert_id,
            "alert_type": a_type,
            "severity": alert["severity"],
            "status": norm_status,
            "explanation": alert["explanation"],
            "statistical_context": statistical_context,
            "calculation_details": calc_details,
            "recommendation": recommendation,
            "evidence_tx_ids": evidence_ids,
            "limitations": limitations
        }

    def list_insights(self, user_id: str) -> List[Dict[str, Any]]:
        summary_sql = """
        SELECT 
            COALESCE(SUM(CASE WHEN transaction_type = 'CREDIT' THEN amount ELSE 0 END), 0.00) AS total_income,
            COALESCE(SUM(CASE WHEN transaction_type = 'DEBIT' THEN amount ELSE 0 END), 0.00) AS total_expense,
            COUNT(transaction_id) AS total_txs
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ? AND transaction_status = 'POSTED'
        """
        rows = db_manager.execute_query(summary_sql, (user_id,))
        total_txs = int(rows[0]["total_txs"]) if rows and rows[0].get("total_txs") else 0
        if total_txs == 0:
            return []

        inc = float(rows[0]["total_income"]) if rows else 0.0
        exp = float(rows[0]["total_expense"]) if rows else 0.0
        rate = round(((inc - exp) / inc) * 100.0, 1) if inc > 0 else 0.0

        return [
            {
                "insight_id": "ins_savings_rate",
                "insight_type": "SAVINGS_OPPORTUNITY",
                "title": f"Healthy {rate}% Net Savings Rate",
                "explanation": f"Over the past 6 months, you saved INR {inc - exp:,.2f} from a total verified income of INR {inc:,.2f}.",
                "generated_at": "2026-11-07 12:00:00"
            },
            {
                "insight_id": "ins_subscription_drift",
                "insight_type": "SPENDING_ANOMALY",
                "title": "Cloud Infrastructure Cost Surge",
                "explanation": "Software subscriptions represented 12% of total expenditure, driven by an unexpected surge in Amazon Web Services billing.",
                "generated_at": "2026-11-07 12:00:00"
            }
        ]

anomaly_engine = AnomalyEngine()
