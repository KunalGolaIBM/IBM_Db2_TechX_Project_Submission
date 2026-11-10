-- ==============================================================================
-- Query: 04_calculated_account_balances.sql
-- Description: Computes the live reconciled balance for each account based on
--              opening balance plus total credits minus total debits.
-- Parameters:
--   ?1 = user_id (VARCHAR)
-- ==============================================================================

SELECT 
    a.account_id,
    a.account_name,
    a.account_type,
    a.institution_name,
    a.currency,
    a.opening_balance,
    COALESCE(SUM(CASE WHEN t.transaction_type = 'CREDIT' THEN t.amount ELSE 0 END), 0.00) AS total_credits,
    COALESCE(SUM(CASE WHEN t.transaction_type = 'DEBIT' THEN t.amount ELSE 0 END), 0.00) AS total_debits,
    (a.opening_balance 
        + COALESCE(SUM(CASE WHEN t.transaction_type = 'CREDIT' THEN t.amount ELSE 0 END), 0.00) 
        - COALESCE(SUM(CASE WHEN t.transaction_type = 'DEBIT' THEN t.amount ELSE 0 END), 0.00)
    ) AS current_calculated_balance
FROM FINSIGHT.ACCOUNTS a
LEFT JOIN FINSIGHT.TRANSACTIONS t 
    ON a.account_id = t.account_id 
    AND t.transaction_status = 'POSTED'
WHERE a.user_id = ?
GROUP BY 
    a.account_id, 
    a.account_name, 
    a.account_type, 
    a.institution_name, 
    a.currency, 
    a.opening_balance
ORDER BY a.account_type, a.account_name;
