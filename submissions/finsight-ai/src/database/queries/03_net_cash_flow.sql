-- ==============================================================================
-- Query: 03_net_cash_flow.sql
-- Description: Computes net cash flow (Total Inflow - Total Outflow) for a user.
-- Parameters:
--   ?1 = user_id (VARCHAR)
--   ?2 = start_date (DATE)
--   ?3 = end_date (DATE)
-- ==============================================================================

WITH flow_summary AS (
    SELECT 
        user_id,
        COALESCE(SUM(CASE WHEN transaction_type = 'CREDIT' AND (category_id IS NULL OR category_id != 'cat_transfer') THEN amount ELSE 0 END), 0.00) AS total_inflow,
        COALESCE(SUM(CASE WHEN transaction_type = 'DEBIT' AND (category_id IS NULL OR category_id != 'cat_transfer') THEN amount ELSE 0 END), 0.00) AS total_outflow
    FROM FINSIGHT.TRANSACTIONS
    WHERE user_id = ?
      AND transaction_status = 'POSTED'
      AND transaction_date BETWEEN ? AND ?
    GROUP BY user_id
)
SELECT 
    user_id,
    total_inflow,
    total_outflow,
    (total_inflow - total_outflow) AS net_cash_flow,
    CASE 
        WHEN (total_inflow - total_outflow) >= 0 THEN 'POSITIVE_SURPLUS'
        ELSE 'DEFICIT_BURN'
    END AS flow_health_status
FROM flow_summary;
