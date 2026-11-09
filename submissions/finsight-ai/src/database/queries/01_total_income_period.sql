-- ==============================================================================
-- Query: 01_total_income_period.sql
-- Description: Computes total verified income for a user within a date range.
-- Parameters:
--   ?1 = user_id (VARCHAR)
--   ?2 = start_date (DATE)
--   ?3 = end_date (DATE)
-- ==============================================================================

SELECT 
    t.user_id,
    COUNT(t.transaction_id) AS total_income_tx_count,
    COALESCE(SUM(t.amount), 0.00) AS total_income_amount,
    t.currency
FROM FINSIGHT.TRANSACTIONS t
WHERE t.user_id = ?
  AND t.transaction_type = 'CREDIT'
  AND t.transaction_status = 'POSTED'
  AND t.category_id != 'cat_transfer' -- Exclude internal transfers
  AND t.transaction_date BETWEEN ? AND ?
GROUP BY t.user_id, t.currency;
