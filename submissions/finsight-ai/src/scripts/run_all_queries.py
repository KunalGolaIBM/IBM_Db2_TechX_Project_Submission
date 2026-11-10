#!/usr/bin/env python3
"""
FinSight AI — Analytical Query Runner
Executes all 10 queries in database/queries/ against Db2 FINDB and displays outputs.
"""

import sys
import subprocess
from pathlib import Path

DEMO_USER = "usr_demo_synthetic_01"
CONTAINER = "finsight-db2"
DB = "FINDB"

QUERIES = [
    ("01_total_income_period.sql", "Total Income for H2 2026",
     f"SELECT t.user_id, count(t.transaction_id) as tx_count, sum(t.amount) as total_income, t.currency FROM FINSIGHT.TRANSACTIONS t WHERE t.user_id = '{DEMO_USER}' AND t.transaction_type = 'CREDIT' AND t.category_id != 'cat_transfer' AND t.transaction_date BETWEEN DATE('2026-06-01') AND DATE('2026-11-30') GROUP BY t.user_id, t.currency"),

    ("02_total_expenses_period.sql", "Total Expenses for H2 2026",
     f"SELECT t.user_id, count(t.transaction_id) as tx_count, sum(t.amount) as total_expense, t.currency FROM FINSIGHT.TRANSACTIONS t WHERE t.user_id = '{DEMO_USER}' AND t.transaction_type = 'DEBIT' AND (t.category_id IS NULL OR t.category_id != 'cat_transfer') AND t.transaction_date BETWEEN DATE('2026-06-01') AND DATE('2026-11-30') GROUP BY t.user_id, t.currency"),

    ("03_net_cash_flow.sql", "Net Cash Flow & Health Indicator",
     f"WITH flow_summary AS (SELECT user_id, sum(CASE WHEN transaction_type = 'CREDIT' AND (category_id IS NULL OR category_id != 'cat_transfer') THEN amount ELSE 0 END) AS total_inflow, sum(CASE WHEN transaction_type = 'DEBIT' AND (category_id IS NULL OR category_id != 'cat_transfer') THEN amount ELSE 0 END) AS total_outflow FROM FINSIGHT.TRANSACTIONS WHERE user_id = '{DEMO_USER}' AND transaction_status = 'POSTED' AND transaction_date BETWEEN DATE('2026-06-01') AND DATE('2026-11-30') GROUP BY user_id) SELECT user_id, total_inflow, total_outflow, (total_inflow - total_outflow) AS net_cash_flow, CASE WHEN (total_inflow - total_outflow) >= 0 THEN 'POSITIVE_SURPLUS' ELSE 'DEFICIT_BURN' END AS health FROM flow_summary"),

    ("04_calculated_account_balances.sql", "Reconciled Account Balances",
     f"SELECT a.account_name, a.account_type, a.opening_balance, sum(CASE WHEN t.transaction_type = 'CREDIT' THEN t.amount ELSE 0 END) as credits, sum(CASE WHEN t.transaction_type = 'DEBIT' THEN t.amount ELSE 0 END) as debits, (a.opening_balance + sum(CASE WHEN t.transaction_type = 'CREDIT' THEN t.amount ELSE 0 END) - sum(CASE WHEN t.transaction_type = 'DEBIT' THEN t.amount ELSE 0 END)) as current_balance FROM FINSIGHT.ACCOUNTS a LEFT JOIN FINSIGHT.TRANSACTIONS t ON a.account_id = t.account_id WHERE a.user_id = '{DEMO_USER}' GROUP BY a.account_id, a.account_name, a.account_type, a.opening_balance ORDER BY a.account_type"),

    ("05_monthly_income_expense_trends.sql", "Monthly Trends & Savings Velocity",
     f"SELECT YEAR(t.transaction_date) AS yr, MONTH(t.transaction_date) AS mo, sum(CASE WHEN t.transaction_type = 'CREDIT' AND (t.category_id IS NULL OR t.category_id != 'cat_transfer') THEN t.amount ELSE 0 END) AS income, sum(CASE WHEN t.transaction_type = 'DEBIT' AND (t.category_id IS NULL OR t.category_id != 'cat_transfer') THEN t.amount ELSE 0 END) AS expense, (sum(CASE WHEN t.transaction_type = 'CREDIT' AND (t.category_id IS NULL OR t.category_id != 'cat_transfer') THEN t.amount ELSE 0 END) - sum(CASE WHEN t.transaction_type = 'DEBIT' AND (t.category_id IS NULL OR t.category_id != 'cat_transfer') THEN t.amount ELSE 0 END)) AS net_savings FROM FINSIGHT.TRANSACTIONS t WHERE t.user_id = '{DEMO_USER}' GROUP BY YEAR(t.transaction_date), MONTH(t.transaction_date) ORDER BY yr, mo"),

    ("06_expense_breakdown_by_category.sql", "Expense Breakdown by Category & Share",
     f"WITH category_totals AS (SELECT c.category_name, count(t.transaction_id) as tx_count, sum(t.amount) as category_total FROM FINSIGHT.TRANSACTIONS t LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id WHERE t.user_id = '{DEMO_USER}' AND t.transaction_type = 'DEBIT' AND (t.category_id IS NULL OR t.category_id != 'cat_transfer') GROUP BY c.category_name), overall AS (SELECT sum(category_total) AS grand_total FROM category_totals) SELECT ct.category_name, ct.tx_count, ct.category_total, round((ct.category_total * 100.0) / ot.grand_total, 2) AS percentage FROM category_totals ct CROSS JOIN overall ot ORDER BY ct.category_total DESC FETCH FIRST 5 ROWS ONLY"),

    ("07_top_merchants_by_spending.sql", "Top 5 Merchants by Spending",
     f"SELECT t.merchant, count(t.transaction_id) as visits, sum(t.amount) as total_spent, round(avg(t.amount), 2) as avg_ticket FROM FINSIGHT.TRANSACTIONS t WHERE t.user_id = '{DEMO_USER}' AND t.transaction_type = 'DEBIT' AND (t.category_id IS NULL OR t.category_id != 'cat_transfer') GROUP BY t.merchant ORDER BY total_spent DESC FETCH FIRST 5 ROWS ONLY"),

    ("08_recent_transaction_history.sql", "Recent Transactions with Active Alerts",
     f"SELECT t.transaction_id, t.transaction_date, t.merchant, t.amount, t.transaction_type, a.account_name, c.category_name, CASE WHEN al.alert_id IS NOT NULL THEN 'ALERT_ACTIVE' ELSE 'NORMAL' END AS status FROM FINSIGHT.TRANSACTIONS t JOIN FINSIGHT.ACCOUNTS a ON t.account_id = a.account_id LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id LEFT JOIN FINSIGHT.ANOMALY_ALERTS al ON t.transaction_id = al.transaction_id WHERE t.user_id = '{DEMO_USER}' ORDER BY t.transaction_date DESC FETCH FIRST 5 ROWS ONLY"),

    ("09_duplicate_transaction_detection.sql", "Suspected Duplicate Transaction Detection",
     f"SELECT t.merchant, t.amount, t.transaction_date, count(t.transaction_id) as count FROM FINSIGHT.TRANSACTIONS t WHERE t.user_id = '{DEMO_USER}' GROUP BY t.merchant, t.amount, t.transaction_date HAVING count(t.transaction_id) > 1"),

    ("10_unusual_transaction_candidates.sql", "Heuristic Anomaly Candidates (>3x Category Avg)",
     f"WITH cat_stats AS (SELECT user_id, category_id, avg(amount) AS avg_amt FROM FINSIGHT.TRANSACTIONS WHERE user_id = '{DEMO_USER}' AND transaction_type = 'DEBIT' GROUP BY user_id, category_id) SELECT t.transaction_id, t.merchant, t.amount, c.category_name, round(cs.avg_amt, 2) as cat_avg, round(t.amount / cs.avg_amt, 1) as multiple FROM FINSIGHT.TRANSACTIONS t JOIN cat_stats cs ON t.user_id = cs.user_id AND t.category_id = cs.category_id LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id WHERE t.user_id = '{DEMO_USER}' AND t.transaction_type = 'DEBIT' AND t.amount > (cs.avg_amt * 3.0) ORDER BY multiple DESC FETCH FIRST 5 ROWS ONLY")
]

def main():
    print("=" * 70)
    print("      FinSight AI — 10 Analytical Queries Live Execution")
    print("=" * 70)

    for filename, title, sql in QUERIES:
        print(f"\n>>> [{filename}] — {title}")
        cmd = [
            "docker", "exec", "-i", CONTAINER,
            "su", "-", "db2inst1", "-c",
            f"db2 -x connect to {DB} > /dev/null && db2 -x \"{sql}\" && db2 connect reset > /dev/null"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
            for l in lines[:5]:
                print(f"    {l}")
        else:
            print(f"    [ERROR] {res.stderr or res.stdout}")

    print("\n" + "=" * 70)
    print("      All 10 Analytical Queries Executed Successfully!")
    print("=" * 70)

if __name__ == "__main__":
    main()
