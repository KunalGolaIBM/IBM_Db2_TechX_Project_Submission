-- ==============================================================================
-- Query: 05_monthly_income_expense_trends.sql
-- Description: Computes month-over-month income, expense, and savings rates.
-- Parameters:
--   ?1 = user_id (VARCHAR)
-- ==============================================================================

SELECT 
    YEAR(t.transaction_date) AS tx_year,
    MONTH(t.transaction_date) AS tx_month,
    COALESCE(SUM(CASE WHEN t.transaction_type = 'CREDIT' AND (t.category_id IS NULL OR t.category_id != 'cat_transfer') THEN t.amount ELSE 0 END), 0.00) AS total_monthly_income,
    COALESCE(SUM(CASE WHEN t.transaction_type = 'DEBIT' AND (t.category_id IS NULL OR t.category_id != 'cat_transfer') THEN t.amount ELSE 0 END), 0.00) AS total_monthly_expense,
    (
        COALESCE(SUM(CASE WHEN t.transaction_type = 'CREDIT' AND (t.category_id IS NULL OR t.category_id != 'cat_transfer') THEN t.amount ELSE 0 END), 0.00)
        - COALESCE(SUM(CASE WHEN t.transaction_type = 'DEBIT' AND (t.category_id IS NULL OR t.category_id != 'cat_transfer') THEN t.amount ELSE 0 END), 0.00)
    ) AS monthly_net_savings,
    COUNT(t.transaction_id) AS total_transactions
FROM FINSIGHT.TRANSACTIONS t
WHERE t.user_id = ?
  AND t.transaction_status = 'POSTED'
GROUP BY YEAR(t.transaction_date), MONTH(t.transaction_date)
ORDER BY tx_year ASC, tx_month ASC;
