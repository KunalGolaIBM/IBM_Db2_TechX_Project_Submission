-- ==============================================================================
-- Query: 10_unusual_transaction_candidates.sql
-- Description: Unsupervised heuristic anomaly detection identifying transactions
--              exceeding 3.0x the user's category spending average.
-- Parameters:
--   ?1 = user_id (VARCHAR)
-- ==============================================================================

WITH category_stats AS (
    SELECT 
        user_id,
        category_id,
        AVG(amount) AS avg_cat_amount,
        COUNT(transaction_id) AS sample_size
    FROM FINSIGHT.TRANSACTIONS
    WHERE user_id = ?
      AND transaction_type = 'DEBIT'
      AND transaction_status = 'POSTED'
    GROUP BY user_id, category_id
    HAVING COUNT(transaction_id) >= 3
)
SELECT 
    t.transaction_id,
    t.transaction_date,
    t.merchant,
    t.description,
    t.amount,
    c.category_name,
    ROUND(cs.avg_cat_amount, 2) AS category_average,
    ROUND(t.amount / cs.avg_cat_amount, 1) AS multiple_of_average,
    'CATEGORY_OUTLIER' AS anomaly_flag
FROM FINSIGHT.TRANSACTIONS t
JOIN category_stats cs 
    ON t.user_id = cs.user_id 
    AND t.category_id = cs.category_id
LEFT JOIN FINSIGHT.CATEGORIES c 
    ON t.category_id = c.category_id
WHERE t.user_id = ?
  AND t.transaction_type = 'DEBIT'
  AND t.amount > (cs.avg_cat_amount * 3.0)
ORDER BY multiple_of_average DESC, t.amount DESC;
