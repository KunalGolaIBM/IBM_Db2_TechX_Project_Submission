-- ==============================================================================
-- Query: 06_expense_breakdown_by_category.sql
-- Description: Groups expenses by category with aggregate amounts and shares.
-- Parameters:
--   ?1 = user_id (VARCHAR)
--   ?2 = start_date (DATE)
--   ?3 = end_date (DATE)
-- ==============================================================================

WITH category_totals AS (
    SELECT 
        COALESCE(c.category_name, 'Uncategorized') AS category_name,
        c.category_id,
        COUNT(t.transaction_id) AS tx_count,
        SUM(t.amount) AS category_total
    FROM FINSIGHT.TRANSACTIONS t
    LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
    WHERE t.user_id = ?
      AND t.transaction_type = 'DEBIT'
      AND t.transaction_status = 'POSTED'
      AND (t.category_id IS NULL OR t.category_id != 'cat_transfer')
      AND t.transaction_date BETWEEN ? AND ?
    GROUP BY c.category_name, c.category_id
),
overall_total AS (
    SELECT SUM(category_total) AS grand_total FROM category_totals
)
SELECT 
    ct.category_id,
    ct.category_name,
    ct.tx_count,
    ct.category_total,
    ROUND((ct.category_total * 100.0) / ot.grand_total, 2) AS percentage_of_total_spend
FROM category_totals ct
CROSS JOIN overall_total ot
ORDER BY ct.category_total DESC;
