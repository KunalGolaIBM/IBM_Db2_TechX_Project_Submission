-- ==============================================================================
-- Query: 09_duplicate_transaction_detection.sql
-- Description: Identifies suspected duplicate charges (same user, account, amount,
--              merchant, and transaction date).
-- Parameters:
--   ?1 = user_id (VARCHAR)
-- ==============================================================================

SELECT 
    t.account_id,
    a.account_name,
    t.merchant,
    t.amount,
    t.transaction_date,
    COUNT(t.transaction_id) AS occurrence_count,
    LISTAGG(t.transaction_id, ', ') WITHIN GROUP (ORDER BY t.transaction_id) AS suspected_transaction_ids
FROM FINSIGHT.TRANSACTIONS t
JOIN FINSIGHT.ACCOUNTS a ON t.account_id = a.account_id
WHERE t.user_id = ?
  AND t.transaction_status = 'POSTED'
GROUP BY 
    t.account_id, 
    a.account_name, 
    t.merchant, 
    t.amount, 
    t.transaction_date
HAVING COUNT(t.transaction_id) > 1
ORDER BY occurrence_count DESC, t.transaction_date DESC;
