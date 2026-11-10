from typing import Dict, Any, List, Optional
from app.db import db_manager

class FinancialTools:
    """
    Controlled set of approved, parameterized financial analysis tools.
    Every metric is deterministically calculated directly inside IBM Db2.
    """

    @staticmethod
    def get_income(user_id: str, start_date: str = "2026-06-01", end_date: str = "2026-11-07") -> Dict[str, Any]:
        sql = """
        SELECT 
            COUNT(transaction_id) AS tx_count,
            COALESCE(SUM(amount), 0.00) AS total_income,
            currency
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ?
          AND transaction_type = 'CREDIT'
          AND transaction_status = 'POSTED'
          AND category_id != 'cat_transfer'
          AND transaction_date BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
        GROUP BY currency
        """
        rows = db_manager.execute_query(sql, (user_id, start_date, end_date))
        total = float(rows[0]["total_income"]) if rows else 0.00
        count = int(rows[0]["tx_count"]) if rows else 0
        currency = rows[0]["currency"] if rows else "INR"

        return {
            "tool": "get_income",
            "period": {"start": start_date, "end": end_date},
            "total_income": total,
            "transaction_count": count,
            "currency": currency,
            "source_table": "FINSIGHT.TRANSACTIONS"
        }

    @staticmethod
    def get_expenses(user_id: str, start_date: str = "2026-06-01", end_date: str = "2026-11-07") -> Dict[str, Any]:
        sql = """
        SELECT 
            COUNT(transaction_id) AS tx_count,
            COALESCE(SUM(amount), 0.00) AS total_expense,
            currency
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ?
          AND transaction_type = 'DEBIT'
          AND transaction_status = 'POSTED'
          AND (category_id IS NULL OR category_id != 'cat_transfer')
          AND transaction_date BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
        GROUP BY currency
        """
        rows = db_manager.execute_query(sql, (user_id, start_date, end_date))
        total = float(rows[0]["total_expense"]) if rows else 0.00
        count = int(rows[0]["tx_count"]) if rows else 0
        currency = rows[0]["currency"] if rows else "INR"

        return {
            "tool": "get_expenses",
            "period": {"start": start_date, "end": end_date},
            "total_expense": total,
            "transaction_count": count,
            "currency": currency,
            "source_table": "FINSIGHT.TRANSACTIONS"
        }

    @staticmethod
    def get_net_cash_flow(user_id: str, start_date: str = "2026-06-01", end_date: str = "2026-11-07") -> Dict[str, Any]:
        sql = """
        WITH flow_summary AS (
            SELECT 
                user_id,
                COALESCE(SUM(CASE WHEN transaction_type = 'CREDIT' AND (category_id IS NULL OR category_id != 'cat_transfer') THEN amount ELSE 0 END), 0.00) AS total_inflow,
                COALESCE(SUM(CASE WHEN transaction_type = 'DEBIT' AND (category_id IS NULL OR category_id != 'cat_transfer') THEN amount ELSE 0 END), 0.00) AS total_outflow
            FROM FINSIGHT.TRANSACTIONS
            WHERE user_id = ?
              AND transaction_status = 'POSTED'
              AND transaction_date BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
            GROUP BY user_id
        )
        SELECT 
            total_inflow,
            total_outflow,
            (total_inflow - total_outflow) AS net_cash_flow
        FROM flow_summary
        """
        rows = db_manager.execute_query(sql, (user_id, start_date, end_date))
        inflow = float(rows[0]["total_inflow"]) if rows else 0.00
        outflow = float(rows[0]["total_outflow"]) if rows else 0.00
        net = float(rows[0]["net_cash_flow"]) if rows else 0.00

        return {
            "tool": "get_net_cash_flow",
            "period": {"start": start_date, "end": end_date},
            "total_inflow": inflow,
            "total_outflow": outflow,
            "net_cash_flow": net,
            "health_status": "POSITIVE_SURPLUS" if net >= 0 else "DEFICIT_BURN"
        }

    @staticmethod
    def get_monthly_trends(user_id: str) -> List[Dict[str, Any]]:
        sql = """
        SELECT 
            YEAR(transaction_date) AS yr,
            MONTH(transaction_date) AS mo,
            COALESCE(SUM(CASE WHEN transaction_type = 'CREDIT' AND (category_id IS NULL OR category_id != 'cat_transfer') THEN amount ELSE 0 END), 0.00) AS income,
            COALESCE(SUM(CASE WHEN transaction_type = 'DEBIT' AND (category_id IS NULL OR category_id != 'cat_transfer') THEN amount ELSE 0 END), 0.00) AS expense
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ?
          AND transaction_status = 'POSTED'
        GROUP BY YEAR(transaction_date), MONTH(transaction_date)
        ORDER BY yr ASC, mo ASC
        """
        rows = db_manager.execute_query(sql, (user_id,))
        return [
            {
                "year": int(r["yr"]),
                "month": int(r["mo"]),
                "income": float(r["income"]),
                "expense": float(r["expense"]),
                "net_savings": float(r["income"]) - float(r["expense"])
            }
            for r in rows
        ]

    @staticmethod
    def get_category_breakdown(user_id: str, start_date: str = "2026-06-01", end_date: str = "2026-11-07") -> List[Dict[str, Any]]:
        sql = """
        WITH category_totals AS (
            SELECT 
                COALESCE(c.category_name, 'Uncategorized') AS category_name,
                COUNT(t.transaction_id) AS tx_count,
                SUM(t.amount) AS category_total
            FROM FINSIGHT.TRANSACTIONS t
            LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
            WHERE t.user_id = ?
              AND t.transaction_type = 'DEBIT'
              AND t.transaction_status = 'POSTED'
              AND (t.category_id IS NULL OR t.category_id != 'cat_transfer')
              AND t.transaction_date BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
            GROUP BY c.category_name
        ),
        overall AS (
            SELECT SUM(category_total) AS grand_total FROM category_totals
        )
        SELECT 
            ct.category_name,
            ct.tx_count,
            ct.category_total,
            ROUND((ct.category_total * 100.0) / ot.grand_total, 2) AS percentage
        FROM category_totals ct
        CROSS JOIN overall ot
        ORDER BY ct.category_total DESC
        """
        rows = db_manager.execute_query(sql, (user_id, start_date, end_date))
        return [
            {
                "category": r["category_name"],
                "transaction_count": int(r["tx_count"]),
                "total_amount": float(r["category_total"]),
                "percentage_of_spend": float(r["percentage"])
            }
            for r in rows
        ]

    @staticmethod
    def get_top_merchants(user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        sql = """
        SELECT 
            merchant,
            COUNT(transaction_id) AS visit_count,
            SUM(amount) AS total_spent,
            ROUND(AVG(amount), 2) AS avg_ticket
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ?
          AND transaction_type = 'DEBIT'
          AND transaction_status = 'POSTED'
          AND (category_id IS NULL OR category_id != 'cat_transfer')
        GROUP BY merchant
        ORDER BY total_spent DESC
        FETCH FIRST ? ROWS ONLY
        """
        rows = db_manager.execute_query(sql, (user_id, limit))
        return [
            {
                "merchant": r["merchant"],
                "visits": int(r["visit_count"]),
                "total_spent": float(r["total_spent"]),
                "average_ticket": float(r["avg_ticket"])
            }
            for r in rows
        ]

    @staticmethod
    def get_recent_transactions(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        sql = """
        SELECT 
            t.transaction_id,
            t.transaction_date,
            t.merchant,
            t.amount,
            t.currency,
            t.transaction_type,
            t.transaction_status,
            a.account_name,
            COALESCE(c.category_name, 'Uncategorized') AS category_name,
            CASE WHEN al.alert_id IS NOT NULL THEN 1 ELSE 0 END AS has_alert
        FROM FINSIGHT.TRANSACTIONS t
        JOIN FINSIGHT.ACCOUNTS a ON t.account_id = a.account_id
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        LEFT JOIN FINSIGHT.ANOMALY_ALERTS al ON t.transaction_id = al.transaction_id
        WHERE t.user_id = ?
        ORDER BY t.transaction_date DESC
        FETCH FIRST ? ROWS ONLY
        """
        rows = db_manager.execute_query(sql, (user_id, limit))
        return [
            {
                "transaction_id": r["transaction_id"],
                "date": str(r["transaction_date"]),
                "merchant": r["merchant"],
                "amount": float(r["amount"]),
                "currency": r["currency"],
                "type": r["transaction_type"],
                "status": r["transaction_status"],
                "account": r["account_name"],
                "category": r["category_name"],
                "has_alert": bool(r["has_alert"])
            }
            for r in rows
        ]

    @staticmethod
    def detect_duplicates(user_id: str) -> List[Dict[str, Any]]:
        sql = """
        SELECT 
            merchant,
            amount,
            transaction_date,
            COUNT(transaction_id) AS count,
            LISTAGG(transaction_id, ', ') WITHIN GROUP (ORDER BY transaction_id) AS tx_ids
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ?
          AND transaction_status = 'POSTED'
        GROUP BY merchant, amount, transaction_date
        HAVING COUNT(transaction_id) > 1
        """
        rows = db_manager.execute_query(sql, (user_id,))
        return [
            {
                "merchant": r["merchant"],
                "amount": float(r["amount"]),
                "date": str(r["transaction_date"]),
                "occurrences": int(r["count"]),
                "transaction_ids": [x.strip() for x in r["tx_ids"].split(",")]
            }
            for r in rows
        ]

    @staticmethod
    def detect_unusual_candidates(user_id: str) -> List[Dict[str, Any]]:
        sql = """
        WITH cat_stats AS (
            SELECT user_id, category_id, AVG(amount) AS avg_amt
            FROM FINSIGHT.TRANSACTIONS
            WHERE user_id = ? AND transaction_type = 'DEBIT' AND transaction_status = 'POSTED'
            GROUP BY user_id, category_id
            HAVING COUNT(transaction_id) >= 3
        )
        SELECT 
            t.transaction_id,
            t.transaction_date,
            t.merchant,
            t.amount,
            COALESCE(c.category_name, 'Uncategorized') AS category_name,
            ROUND(cs.avg_amt, 2) AS category_average,
            ROUND(t.amount / cs.avg_amt, 1) AS multiple
        FROM FINSIGHT.TRANSACTIONS t
        JOIN cat_stats cs ON t.user_id = cs.user_id AND t.category_id = cs.category_id
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE t.user_id = ?
          AND t.transaction_type = 'DEBIT'
          AND t.transaction_status = 'POSTED'
          AND t.amount > (cs.avg_amt * 3.0)
        ORDER BY multiple DESC
        """
        rows = db_manager.execute_query(sql, (user_id, user_id))
        return [
            {
                "transaction_id": r["transaction_id"],
                "date": str(r["transaction_date"]),
                "merchant": r["merchant"],
                "category": r["category_name"],
                "amount": float(r["amount"]),
                "category_average": float(r["category_average"]),
                "multiple_of_average": float(r["multiple"])
            }
            for r in rows
        ]

    @staticmethod
    def get_category_spending(
        user_id: str,
        category_query: str,
        start_date: str = "2026-06-01",
        end_date: str = "2026-11-07"
    ) -> Dict[str, Any]:
        """Calculates total spend and returns top items for a specific category within a date window."""
        cat_pattern = f"%{category_query.strip().lower()}%"
        sql = """
        SELECT 
            COUNT(t.transaction_id) AS tx_count,
            COALESCE(SUM(t.amount), 0.00) AS total_spent,
            COALESCE(MAX(c.category_name), 'Unknown') AS category_name,
            t.currency
        FROM FINSIGHT.TRANSACTIONS t
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE t.user_id = ?
          AND t.transaction_type = 'DEBIT'
          AND t.transaction_status = 'POSTED'
          AND (t.category_id IS NULL OR t.category_id != 'cat_transfer')
          AND (LOWER(c.category_name) LIKE ? OR LOWER(t.category_id) LIKE ?)
          AND t.transaction_date BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
        GROUP BY t.currency
        """
        rows = db_manager.execute_query(sql, (user_id, cat_pattern, cat_pattern, start_date, end_date))
        total = float(rows[0]["total_spent"]) if rows else 0.00
        count = int(rows[0]["tx_count"]) if rows else 0
        cat_name = rows[0]["category_name"] if rows else category_query.title()
        currency = rows[0]["currency"] if rows else "INR"

        # Also get top 5 transactions for context
        tx_sql = """
        SELECT t.transaction_id, t.transaction_date, t.merchant, t.amount, t.description
        FROM FINSIGHT.TRANSACTIONS t
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE t.user_id = ?
          AND t.transaction_type = 'DEBIT'
          AND t.transaction_status = 'POSTED'
          AND (t.category_id IS NULL OR t.category_id != 'cat_transfer')
          AND (LOWER(c.category_name) LIKE ? OR LOWER(t.category_id) LIKE ?)
          AND t.transaction_date BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
        ORDER BY t.amount DESC
        FETCH FIRST 5 ROWS ONLY
        """
        tx_rows = db_manager.execute_query(tx_sql, (user_id, cat_pattern, cat_pattern, start_date, end_date))
        items = [
            {
                "transaction_id": r["transaction_id"],
                "date": str(r["transaction_date"]),
                "merchant": r["merchant"],
                "amount": float(r["amount"]),
                "description": r.get("description") or ""
            }
            for r in tx_rows
        ]

        return {
            "category": cat_name,
            "period": {"start": start_date, "end": end_date},
            "total_spent": total,
            "transaction_count": count,
            "currency": currency,
            "top_transactions": items
        }

    @staticmethod
    def get_biggest_expenses(
        user_id: str,
        start_date: str = "2026-06-01",
        end_date: str = "2026-11-07",
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieves largest individual debits within a date window (excluding internal transfers)."""
        sql = """
        SELECT t.transaction_id, t.transaction_date, t.merchant, t.amount, t.currency,
               COALESCE(c.category_name, 'Uncategorized') AS category_name, t.description
        FROM FINSIGHT.TRANSACTIONS t
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE t.user_id = ?
          AND t.transaction_type = 'DEBIT'
          AND t.transaction_status = 'POSTED'
          AND (t.category_id IS NULL OR t.category_id != 'cat_transfer')
          AND t.transaction_date BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
        ORDER BY t.amount DESC
        FETCH FIRST ? ROWS ONLY
        """
        rows = db_manager.execute_query(sql, (user_id, start_date, end_date, limit))
        return [
            {
                "transaction_id": r["transaction_id"],
                "date": str(r["transaction_date"]),
                "merchant": r["merchant"],
                "amount": float(r["amount"]),
                "currency": r["currency"],
                "category": r["category_name"],
                "description": r.get("description") or ""
            }
            for r in rows
        ]

    @staticmethod
    def get_subscriptions(user_id: str, limit: int = 8) -> List[Dict[str, Any]]:
        """Retrieves recurring subscriptions and digital services."""
        sql = """
        SELECT t.transaction_id, t.transaction_date, t.merchant, t.amount, t.currency,
               t.transaction_status, COALESCE(c.category_name, 'Subscriptions') AS category_name,
               t.description
        FROM FINSIGHT.TRANSACTIONS t
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE t.user_id = ?
          AND (t.category_id = 'cat_subscriptions' 
               OR LOWER(t.merchant) IN ('netflix india', 'spotify india', 'github inc.', 'amazon web services', 'airtel fiber broadband', 'cult.fit prime gym'))
        ORDER BY t.transaction_date DESC
        FETCH FIRST ? ROWS ONLY
        """
        rows = db_manager.execute_query(sql, (user_id, limit))
        return [
            {
                "transaction_id": r["transaction_id"],
                "date": str(r["transaction_date"]),
                "merchant": r["merchant"],
                "amount": float(r["amount"]),
                "currency": r["currency"],
                "status": r["transaction_status"],
                "category": r["category_name"],
                "description": r.get("description") or ""
            }
            for r in rows
        ]

    @staticmethod
    def get_pending_transactions(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves unposted pending transactions awaiting clearing."""
        sql = """
        SELECT t.transaction_id, t.transaction_date, t.merchant, t.amount, t.currency,
               COALESCE(c.category_name, 'Uncategorized') AS category_name, t.description
        FROM FINSIGHT.TRANSACTIONS t
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE t.user_id = ?
          AND t.transaction_status = 'PENDING'
        ORDER BY t.transaction_date ASC
        FETCH FIRST ? ROWS ONLY
        """
        rows = db_manager.execute_query(sql, (user_id, limit))
        return [
            {
                "transaction_id": r["transaction_id"],
                "date": str(r["transaction_date"]),
                "merchant": r["merchant"],
                "amount": float(r["amount"]),
                "currency": r["currency"],
                "category": r["category_name"],
                "description": r.get("description") or ""
            }
            for r in rows
        ]

    @staticmethod
    def compare_monthly_cash_flow(user_id: str, months_count: int = 3) -> List[Dict[str, Any]]:
        """Compares income, outflow, and net cash flow across recent months."""
        sql = """
        SELECT 
            VARCHAR_FORMAT(transaction_date, 'YYYY-MM') AS month_year,
            COALESCE(SUM(CASE WHEN transaction_type = 'CREDIT' AND transaction_status = 'POSTED' THEN amount ELSE 0 END), 0.00) AS income,
            COALESCE(SUM(CASE WHEN transaction_type = 'DEBIT' AND transaction_status = 'POSTED' AND (category_id IS NULL OR category_id != 'cat_transfer') THEN amount ELSE 0 END), 0.00) AS expense
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ?
        GROUP BY VARCHAR_FORMAT(transaction_date, 'YYYY-MM')
        ORDER BY month_year DESC
        FETCH FIRST ? ROWS ONLY
        """
        rows = db_manager.execute_query(sql, (user_id, months_count))
        # Reverse to chronological order
        chronological = list(reversed(rows))
        return [
            {
                "month": r["month_year"].strip(),
                "income": float(r["income"]),
                "expense": float(r["expense"]),
                "net": float(r["income"]) - float(r["expense"])
            }
            for r in chronological
        ]

    @staticmethod
    def get_monthly_savings(user_id: str, month_str: Optional[str] = None) -> Dict[str, Any]:
        """Calculates income, expenditure, and net savings for a specific calendar month."""
        if not month_str:
            month_str = "2026-11"
        is_current_mtd = (month_str == "2026-11")

        sql = """
        SELECT 
            COALESCE(SUM(CASE WHEN transaction_type = 'CREDIT' AND transaction_status = 'POSTED' THEN amount ELSE 0 END), 0.00) AS income,
            COALESCE(SUM(CASE WHEN transaction_type = 'DEBIT' AND transaction_status = 'POSTED' AND (category_id IS NULL OR category_id != 'cat_transfer') THEN amount ELSE 0 END), 0.00) AS expense
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ?
          AND VARCHAR_FORMAT(transaction_date, 'YYYY-MM') = ?
        """
        rows = db_manager.execute_query(sql, (user_id, month_str))
        income = float(rows[0]["income"]) if rows else 0.00
        expense = float(rows[0]["expense"]) if rows else 0.00
        net = income - expense
        rate = round((net / income * 100.0), 1) if income > 0 else 0.0

        return {
            "month": month_str,
            "is_mtd": is_current_mtd,
            "income": income,
            "expense": expense,
            "net_savings": net,
            "savings_rate_percent": rate
        }

financial_tools = FinancialTools()
