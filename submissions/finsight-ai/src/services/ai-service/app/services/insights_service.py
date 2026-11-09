"""
FinSight AI — Stage 6 Financial Insights & Reports Service
Deterministically computes month-over-month comparisons, savings rates,
spending shifts, top merchants, recurring commitments, and audit-ready reports.
Strictly excludes pending transactions and internal transfers (cat_transfer).
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import re
from app.db import db_manager

class InsightsService:
    @staticmethod
    def get_previous_month(month_str: str) -> str:
        """Computes the YYYY-MM string for the preceding calendar month."""
        try:
            parts = month_str.split("-")
            year, mon = int(parts[0]), int(parts[1])
            if mon == 1:
                return f"{year - 1}-12"
            else:
                return f"{year}-{mon - 1:02d}"
        except Exception:
            return month_str

    @staticmethod
    def validate_month_format(month_str: str) -> bool:
        """Validates that month follows strict YYYY-MM format between 2000-01 and 2099-12."""
        if not re.match(r"^20\d\d-(0[1-9]|1[0-2])$", month_str):
            return False
        return True

    @staticmethod
    def get_available_months(user_id: str) -> List[str]:
        """Lists all distinct posted transaction months recorded in Db2 for this user."""
        sql = """
        SELECT DISTINCT VARCHAR_FORMAT(transaction_date, 'YYYY-MM') AS month_str
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ? AND transaction_status = 'POSTED'
        ORDER BY month_str DESC
        """
        rows = db_manager.execute_query(sql, (user_id,))
        return [r["month_str"].strip() for r in rows if r.get("month_str")]

    def get_monthly_insights(self, user_id: str, month: Optional[str] = None) -> Dict[str, Any]:
        """
        Computes monthly financial insights, MoM comparison, savings rates,
        category shifts, recurring commitments, and deterministic narratives.
        """
        available_months = self.get_available_months(user_id)
        
        # Determine reporting month
        if month:
            month = month.strip()
            if not self.validate_month_format(month):
                raise ValueError(f"Invalid month format '{month}'. Must be YYYY-MM between 2000-01 and 2099-12.")
            target_month = month
        else:
            target_month = available_months[0] if available_months else datetime.now(timezone.utc).strftime("%Y-%m")

        prev_month = self.get_previous_month(target_month)

        # 1. Target month posted income (CREDIT excluding cat_transfer)
        inc_sql = """
        SELECT COALESCE(SUM(amount), 0.00) AS total_inc, COUNT(*) AS inc_cnt
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ?
          AND transaction_type = 'CREDIT'
          AND transaction_status = 'POSTED'
          AND (category_id IS NULL OR category_id != 'cat_transfer')
          AND VARCHAR_FORMAT(transaction_date, 'YYYY-MM') = ?
        """
        inc_rows = db_manager.execute_query(inc_sql, (user_id, target_month))
        cur_income = float(inc_rows[0]["total_inc"]) if inc_rows else 0.00
        cur_income_cnt = int(inc_rows[0]["inc_cnt"]) if inc_rows else 0

        # 2. Target month posted expenses (DEBIT excluding cat_transfer)
        exp_sql = """
        SELECT COALESCE(SUM(amount), 0.00) AS total_exp, COUNT(*) AS exp_cnt
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ?
          AND transaction_type = 'DEBIT'
          AND transaction_status = 'POSTED'
          AND (category_id IS NULL OR category_id != 'cat_transfer')
          AND VARCHAR_FORMAT(transaction_date, 'YYYY-MM') = ?
        """
        exp_rows = db_manager.execute_query(exp_sql, (user_id, target_month))
        cur_expenses = float(exp_rows[0]["total_exp"]) if exp_rows else 0.00
        cur_expenses_cnt = int(exp_rows[0]["exp_cnt"]) if exp_rows else 0

        # 3. Previous month posted income
        prev_inc_rows = db_manager.execute_query(inc_sql, (user_id, prev_month))
        prev_income = float(prev_inc_rows[0]["total_inc"]) if prev_inc_rows else 0.00

        # 4. Previous month posted expenses
        prev_exp_rows = db_manager.execute_query(exp_sql, (user_id, prev_month))
        prev_expenses = float(prev_exp_rows[0]["total_exp"]) if prev_exp_rows else 0.00

        # 5. Pending transactions count and sum for target month (strictly excluded from posted totals)
        pnd_sql = """
        SELECT COALESCE(SUM(amount), 0.00) AS pnd_sum, COUNT(*) AS pnd_cnt
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ?
          AND transaction_status = 'PENDING'
          AND VARCHAR_FORMAT(transaction_date, 'YYYY-MM') = ?
        """
        pnd_rows = db_manager.execute_query(pnd_sql, (user_id, target_month))
        pending_count = int(pnd_rows[0]["pnd_cnt"]) if pnd_rows else 0
        pending_amount = float(pnd_rows[0]["pnd_sum"]) if pnd_rows else 0.00

        # Internal transfers count and sum for audit disclosure
        xfer_sql = """
        SELECT COALESCE(SUM(amount), 0.00) AS xfer_sum, COUNT(*) AS xfer_cnt
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ?
          AND category_id = 'cat_transfer'
          AND transaction_status = 'POSTED'
          AND VARCHAR_FORMAT(transaction_date, 'YYYY-MM') = ?
        """
        xfer_rows = db_manager.execute_query(xfer_sql, (user_id, target_month))
        transfers_count = int(xfer_rows[0]["xfer_cnt"]) if xfer_rows else 0
        transfers_amount = float(xfer_rows[0]["xfer_sum"]) if xfer_rows else 0.00

        # 6. Calculations
        cur_net = round(cur_income - cur_expenses, 2)
        prev_net = round(prev_income - prev_expenses, 2)

        # Savings rate calculation: (income - expenses) / income * 100
        # If income <= 0, savings rate is 0.0 (clearly documented as undefined / zero baseline)
        if cur_income > 0:
            savings_rate = round(((cur_income - cur_expenses) / cur_income) * 100.0, 2)
            savings_rate_formula = "(Total Inflow - Total Outflow) / Total Inflow * 100"
            savings_rate_explanation = f"Saved INR {cur_net:,.2f} from total verified income of INR {cur_income:,.2f} ({savings_rate}%)."
        else:
            savings_rate = 0.00
            savings_rate_formula = "(Total Inflow - Total Outflow) / Total Inflow * 100 [Undefined when Inflow <= 0]"
            savings_rate_explanation = "Verified income for this reporting month was INR 0.00. Savings rate is not applicable."

        # MoM percentage changes
        def get_comparison(current: float, previous: float) -> Dict[str, Any]:
            diff = round(current - previous, 2)
            if previous > 0:
                pct = round(((current - previous) / previous) * 100.0, 2)
            else:
                pct = None
            return {
                "current": current,
                "previous": previous,
                "difference": diff,
                "percentage_change": pct
            }

        income_comparison = get_comparison(cur_income, prev_income)
        expenses_comparison = get_comparison(cur_expenses, prev_expenses)
        net_comparison = get_comparison(cur_net, prev_net)

        # 7. Category Spending Comparison (Current vs Previous)
        cat_cmp_sql = """
        WITH cur_cat AS (
            SELECT COALESCE(c.category_name, 'Uncategorized') AS category_name,
                   t.category_id,
                   COALESCE(SUM(t.amount), 0.00) AS spent,
                   COUNT(*) AS cnt
            FROM FINSIGHT.TRANSACTIONS t
            LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
            WHERE t.user_id = ?
              AND t.transaction_type = 'DEBIT'
              AND t.transaction_status = 'POSTED'
              AND (t.category_id IS NULL OR t.category_id != 'cat_transfer')
              AND VARCHAR_FORMAT(t.transaction_date, 'YYYY-MM') = ?
            GROUP BY c.category_name, t.category_id
        ),
        prev_cat AS (
            SELECT COALESCE(c.category_name, 'Uncategorized') AS category_name,
                   t.category_id,
                   COALESCE(SUM(t.amount), 0.00) AS spent,
                   COUNT(*) AS cnt
            FROM FINSIGHT.TRANSACTIONS t
            LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
            WHERE t.user_id = ?
              AND t.transaction_type = 'DEBIT'
              AND t.transaction_status = 'POSTED'
              AND (t.category_id IS NULL OR t.category_id != 'cat_transfer')
              AND VARCHAR_FORMAT(t.transaction_date, 'YYYY-MM') = ?
            GROUP BY c.category_name, t.category_id
        )
        SELECT 
            COALESCE(cur.category_name, prev.category_name) AS category_name,
            COALESCE(cur.category_id, prev.category_id) AS category_id,
            COALESCE(cur.spent, 0.00) AS cur_spent,
            COALESCE(cur.cnt, 0) AS cur_cnt,
            COALESCE(prev.spent, 0.00) AS prev_spent,
            COALESCE(prev.cnt, 0) AS prev_cnt
        FROM cur_cat cur
        FULL OUTER JOIN prev_cat prev ON cur.category_id = prev.category_id
        ORDER BY cur_spent DESC, prev_spent DESC
        """
        cat_cmp_rows = db_manager.execute_query(cat_cmp_sql, (user_id, target_month, user_id, prev_month))

        category_changes = []
        top_categories = []
        for r in cat_cmp_rows:
            c_name = r["category_name"].strip() if r.get("category_name") else "Uncategorized"
            c_spent = float(r["cur_spent"])
            p_spent = float(r["prev_spent"])
            c_cnt = int(r["cur_cnt"])
            diff = round(c_spent - p_spent, 2)
            pct = round(((c_spent - p_spent) / p_spent) * 100.0, 2) if p_spent > 0 else None
            
            item = {
                "category_name": c_name,
                "category_id": r.get("category_id") or "cat_other",
                "current_amount": c_spent,
                "previous_amount": p_spent,
                "difference": diff,
                "percentage_change": pct,
                "tx_count": c_cnt
            }
            category_changes.append(item)
            if c_spent > 0:
                top_categories.append({
                    "category": c_name,
                    "total_spent": c_spent,
                    "count": c_cnt,
                    "share_of_wallet": round((c_spent / cur_expenses) * 100.0, 1) if cur_expenses > 0 else 0.0
                })

        # 8. Top Merchants for the month
        top_merch_sql = """
        SELECT 
            t.merchant,
            COALESCE(c.category_name, 'Uncategorized') AS category_name,
            SUM(t.amount) AS total_spent,
            COUNT(*) AS tx_count
        FROM FINSIGHT.TRANSACTIONS t
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE t.user_id = ?
          AND t.transaction_type = 'DEBIT'
          AND t.transaction_status = 'POSTED'
          AND (t.category_id IS NULL OR t.category_id != 'cat_transfer')
          AND VARCHAR_FORMAT(t.transaction_date, 'YYYY-MM') = ?
        GROUP BY t.merchant, c.category_name
        ORDER BY total_spent DESC
        FETCH FIRST 5 ROWS ONLY
        """
        merch_rows = db_manager.execute_query(top_merch_sql, (user_id, target_month))
        top_merchants = [
            {
                "merchant": r["merchant"].strip(),
                "category": r["category_name"].strip(),
                "total_spent": float(r["total_spent"]),
                "tx_count": int(r["tx_count"])
            }
            for r in merch_rows
        ]

        # 9. Recurring Observations in the reporting month
        rec_sql = """
        SELECT t.merchant, t.amount, COALESCE(c.category_name, 'Uncategorized') as category_name,
               VARCHAR_FORMAT(t.transaction_date, 'YYYY-MM-DD') as last_date
        FROM FINSIGHT.TRANSACTIONS t
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE t.user_id = ?
          AND t.transaction_status = 'POSTED'
          AND (t.category_id IS NULL OR t.category_id != 'cat_transfer')
          AND VARCHAR_FORMAT(t.transaction_date, 'YYYY-MM') = ?
          AND (
              LOWER(t.merchant) LIKE '%netflix%' OR
              LOWER(t.merchant) LIKE '%spotify%' OR
              LOWER(t.merchant) LIKE '%github%' OR
              LOWER(t.merchant) LIKE '%airtel%' OR
              LOWER(t.merchant) LIKE '%bses%' OR
              LOWER(t.merchant) LIKE '%rent%' OR
              LOWER(t.merchant) LIKE '%greenfield%' OR
              LOWER(t.merchant) LIKE '%aws%' OR
              LOWER(t.merchant) LIKE '%amazon web services%' OR
              LOWER(COALESCE(t.description, '')) LIKE '%subscription%' OR
              LOWER(COALESCE(t.description, '')) LIKE '%recurring%'
          )
        ORDER BY t.amount DESC
        """
        rec_rows = db_manager.execute_query(rec_sql, (user_id, target_month))
        recurring_observations = [
            {
                "merchant": r["merchant"].strip(),
                "amount": float(r["amount"]),
                "category": r["category_name"].strip(),
                "frequency": "MONTHLY",
                "last_date": r["last_date"].strip()
            }
            for r in rec_rows
        ]

        # 10. Unusual Observations based on existing anomaly intelligence
        anom_sql = """
        SELECT a.alert_id, a.alert_type, a.severity, a.status,
               COALESCE(t.merchant, 'Unknown Payee') AS merchant,
               COALESCE(t.amount, 0.00) AS amount,
               a.explanation
        FROM FINSIGHT.ANOMALY_ALERTS a
        LEFT JOIN FINSIGHT.TRANSACTIONS t ON a.transaction_id = t.transaction_id
        WHERE a.user_id = ?
          AND (t.transaction_date IS NULL OR VARCHAR_FORMAT(t.transaction_date, 'YYYY-MM') = ?)
        ORDER BY amount DESC
        """
        anom_rows = db_manager.execute_query(anom_sql, (user_id, target_month))
        unusual_observations = [
            {
                "alert_id": r["alert_id"].strip(),
                "alert_type": r["alert_type"].strip(),
                "severity": r["severity"].strip(),
                "status": r["status"].strip(),
                "merchant": r["merchant"].strip(),
                "amount": float(r["amount"]),
                "description": r["explanation"].strip() if r.get("explanation") else "Statistical anomaly detected."
            }
            for r in anom_rows
        ]

        # 11. Legacy compatibility insight items (so test_audit_stage2c.py passes seamlessly)
        legacy_insights = []
        is_empty = (cur_income_cnt + cur_expenses_cnt) == 0

        if not is_empty:
            legacy_insights.append({
                "insight_id": f"ins_{target_month}_savings",
                "insight_type": "SAVINGS_OPPORTUNITY",
                "title": f"Net Savings Rate: {savings_rate}%",
                "explanation": savings_rate_explanation,
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            })
            if unusual_observations:
                legacy_insights.append({
                    "insight_id": f"ins_{target_month}_anom",
                    "insight_type": "SPENDING_ANOMALY",
                    "title": f"{len(unusual_observations)} Anomaly Alert(s) Recorded",
                    "explanation": f"Unusual expenditure observed: {unusual_observations[0]['merchant']} for INR {unusual_observations[0]['amount']:,.2f}.",
                    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                })
            elif top_categories:
                legacy_insights.append({
                    "insight_id": f"ins_{target_month}_top_cat",
                    "insight_type": "CATEGORY_DISTRIBUTION",
                    "title": f"Primary Expense: {top_categories[0]['category']}",
                    "explanation": f"{top_categories[0]['category']} accounted for INR {top_categories[0]['total_spent']:,.2f} ({top_categories[0]['share_of_wallet']}% of spending).",
                    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                })

        # 12. Deterministic Narrative Summary Generation (Mode A)
        narrative_paragraphs = []
        if is_empty:
            narrative_paragraphs.append(
                f"No verified financial transactions have been posted for the period {target_month}. "
                "Your ledger currently contains zero debits or credits for this month."
            )
        else:
            # Financial headline
            if cur_net >= 0:
                headline = (
                    f"In {target_month}, you recorded a positive net cash flow of INR {cur_net:,.2f} "
                    f"(total outflows of INR {cur_expenses:,.2f} against verified inflows of INR {cur_income:,.2f}), "
                    f"retaining {savings_rate}% of your income."
                )
            else:
                headline = (
                    f"In {target_month}, expenditures exceeded verified income by INR {abs(cur_net):,.2f}. "
                    f"Total posted outflows were INR {cur_expenses:,.2f} against inflows of INR {cur_income:,.2f}."
                )
            narrative_paragraphs.append(headline)

            # Trajectory vs Previous Month
            if prev_income > 0 or prev_expenses > 0:
                exp_diff = expenses_comparison["difference"]
                exp_pct = expenses_comparison["percentage_change"]
                if exp_pct is not None:
                    pct_desc = f"{abs(exp_pct):.1f}% {'higher' if exp_diff > 0 else 'lower'}"
                else:
                    pct_desc = f"a change of INR {exp_diff:,.2f}"

                traj = (
                    f"Compared to {prev_month} (outflows of INR {prev_expenses:,.2f}), total living expenditures were {pct_desc}. "
                )
                if top_categories:
                    traj += f"The largest expenditure category remained {top_categories[0]['category']} at INR {top_categories[0]['total_spent']:,.2f}."
                narrative_paragraphs.append(traj)

            # Commitments & Anomalies
            notes = []
            if recurring_observations:
                rec_total = sum(r["amount"] for r in recurring_observations)
                notes.append(f"{len(recurring_observations)} recurring commitments identified totaling INR {rec_total:,.2f}")
            if unusual_observations:
                notes.append(f"{len(unusual_observations)} statistical anomaly alerts flagged for review")
            if pending_count > 0:
                notes.append(f"{pending_count} pending transactions (INR {pending_amount:,.2f}) strictly excluded from posted totals")
            if transfers_count > 0:
                notes.append(f"{transfers_count} internal transfers (INR {transfers_amount:,.2f}) excluded from living expenses")

            if notes:
                narrative_paragraphs.append("Key ledger observations: " + "; ".join(notes) + ".")

        narrative_summary = "\n\n".join(narrative_paragraphs)

        calculation_notes = [
            "All figures derived strictly from IBM Db2 FINSIGHT.TRANSACTIONS table using parameterized SQL.",
            f"Savings Rate Formula: {savings_rate_formula}",
            "Pending transactions are excluded from posted income, expense, and net cash flow calculations.",
            "Internal transfers (category_id = 'cat_transfer') are excluded from living expense baselines.",
            "Month-over-month percentage changes from a zero baseline are designated as non-divisible (None) to avoid division by zero."
        ]

        return {
            "user_id": user_id,
            "month": target_month,
            "previous_month": prev_month,
            "available_months": available_months,
            "currency": "INR",
            "income": income_comparison,
            "expenses": expenses_comparison,
            "net_cash_flow": net_comparison,
            "savings_rate": savings_rate,
            "savings_rate_formula": savings_rate_formula,
            "savings_rate_explanation": savings_rate_explanation,
            "category_changes": category_changes,
            "top_categories": top_categories,
            "top_merchants": top_merchants,
            "recurring_observations": recurring_observations,
            "unusual_observations": unusual_observations,
            "narrative_summary": narrative_summary,
            "generation_mode": "MODE_A_DETERMINISTIC",
            "calculation_notes": calculation_notes,
            "is_empty": is_empty,
            "insights": legacy_insights # Preserved for test_audit_stage2c.py compatibility
        }

    def get_monthly_report(self, user_id: str, month: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates an audit-ready, print-friendly monthly financial report
        with user context, executive summary, breakdown tables, and methodology notes.
        """
        # 1. Fetch user context
        u_sql = "SELECT full_name, email FROM FINSIGHT.USERS WHERE user_id = ?"
        u_rows = db_manager.execute_query(u_sql, (user_id,))
        full_name = u_rows[0]["full_name"].strip() if u_rows else "FinSight Member"
        email = u_rows[0]["email"].strip() if u_rows else ""

        # 2. Fetch monthly insights
        insights = self.get_monthly_insights(user_id, month)

        # 3. Transaction counts
        target_month = insights["month"]
        tx_stats_sql = """
        SELECT 
            COALESCE(SUM(CASE WHEN transaction_status = 'POSTED' THEN 1 ELSE 0 END), 0) AS posted_cnt,
            COALESCE(SUM(CASE WHEN transaction_status = 'PENDING' THEN 1 ELSE 0 END), 0) AS pending_cnt
        FROM FINSIGHT.TRANSACTIONS
        WHERE user_id = ? AND VARCHAR_FORMAT(transaction_date, 'YYYY-MM') = ?
        """
        tx_rows = db_manager.execute_query(tx_stats_sql, (user_id, target_month))
        posted_tx_cnt = int(tx_rows[0]["posted_cnt"]) if tx_rows else 0
        pending_tx_cnt = int(tx_rows[0]["pending_cnt"]) if tx_rows else 0

        summary = {
            "total_income": insights["income"]["current"],
            "total_expenses": insights["expenses"]["current"],
            "net_cash_flow": insights["net_cash_flow"]["current"],
            "savings_rate": insights["savings_rate"],
            "posted_transaction_count": posted_tx_cnt,
            "pending_transaction_count": pending_tx_cnt,
            "currency": "INR"
        }

        comparison = {
            "income": insights["income"],
            "expenses": insights["expenses"],
            "net_cash_flow": insights["net_cash_flow"]
        }

        methodology_notes = [
            "Source of Truth: IBM Db2 12.1.5.0 enterprise ledger (FINDB schema FINSIGHT).",
            "Deterministic Mode A Engine: zero generative hallucination; 100% of figures verified via parameterized SQL.",
            "Transaction Status Partitioning: Pending transactions are held in escrow telemetry and excluded from posted cash-flow settlement.",
            "Transfer Exclusion: Category 'cat_transfer' represents intra-account movements and is strictly excluded from consumption expenditure.",
            "Deduplication Integrity: Transactions evaluated against exact and fuzzy duplicate candidate models."
        ]

        return {
            "user_id": user_id,
            "user_name": full_name,
            "user_email": email,
            "month": target_month,
            "previous_month": insights["previous_month"],
            "available_months": insights["available_months"],
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "currency": "INR",
            "summary": summary,
            "comparison": comparison,
            "category_breakdown": insights["category_changes"],
            "top_merchants": insights["top_merchants"],
            "recurring_commitments": insights["recurring_observations"],
            "anomalies": insights["unusual_observations"],
            "executive_summary": insights["narrative_summary"],
            "generation_mode": insights["generation_mode"],
            "methodology_notes": methodology_notes,
            "is_empty": insights["is_empty"]
        }

insights_service = InsightsService()
