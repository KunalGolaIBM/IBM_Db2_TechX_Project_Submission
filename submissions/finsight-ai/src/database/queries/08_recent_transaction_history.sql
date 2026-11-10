-- ==============================================================================
-- Query: 08_recent_transaction_history.sql
-- Description: Retrieves recent transactions with joined account and category data.
-- Parameters:
--   ?1 = user_id (VARCHAR)
-- ==============================================================================

SELECT 
    t.transaction_id,
    t.transaction_date,
    t.merchant,
    t.description,
    t.amount,
    t.currency,
    t.transaction_type,
    t.transaction_status,
    t.source,
    a.account_name,
    a.account_type,
    COALESCE(c.category_name, 'Uncategorized') AS category_name,
    CASE WHEN al.alert_id IS NOT NULL THEN 1 ELSE 0 END AS has_active_alert
FROM FINSIGHT.TRANSACTIONS t
JOIN FINSIGHT.ACCOUNTS a ON t.account_id = a.account_id
LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
LEFT JOIN FINSIGHT.ANOMALY_ALERTS al ON t.transaction_id = al.transaction_id AND al.status = 'ACTIVE'
WHERE t.user_id = ?
ORDER BY t.transaction_date DESC, t.created_at DESC
FETCH FIRST 50 ROWS ONLY;
