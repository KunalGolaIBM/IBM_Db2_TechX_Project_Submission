-- ==============================================================================
-- Query: 07_top_merchants_by_spending.sql
-- Description: Aggregates top expenditure destinations by merchant.
-- Parameters:
--   ?1 = user_id (VARCHAR)
--   ?2 = start_date (DATE)
--   ?3 = end_date (DATE)
--   ?4 = limit_rows (INTEGER)
-- ==============================================================================

SELECT 
    t.merchant,
    COUNT(t.transaction_id) AS visit_count,
    SUM(t.amount) AS total_spent,
    ROUND(AVG(t.amount), 2) AS average_ticket_size,
    MAX(t.transaction_date) AS most_recent_transaction_date
FROM FINSIGHT.TRANSACTIONS t
WHERE t.user_id = ?
  AND t.transaction_type = 'DEBIT'
  AND t.transaction_status = 'POSTED'
  AND (t.category_id IS NULL OR t.category_id != 'cat_transfer')
  AND t.transaction_date BETWEEN ? AND ?
GROUP BY t.merchant
ORDER BY total_spent DESC
FETCH FIRST 10 ROWS ONLY;
