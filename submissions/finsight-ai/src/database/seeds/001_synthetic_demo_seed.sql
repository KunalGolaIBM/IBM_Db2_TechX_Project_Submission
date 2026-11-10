-- ==============================================================================
-- Seed Script: 001_synthetic_demo_seed.sql
-- Description: Populates synthetic demo user, accounts, categories, and >100
--              realistic financial transactions with idempotent MERGE statements.
-- ==============================================================================

MERGE INTO FINSIGHT.USERS AS target
USING (VALUES ('usr_demo_synthetic_01', 'alex.chen.demo@finsight.internal', 'Alex Chen (Synthetic Demo)')) AS src (user_id, email, full_name)
ON (target.user_id = src.user_id)
WHEN NOT MATCHED THEN
    INSERT (user_id, email, full_name)
    VALUES (src.user_id, src.email, src.full_name);

MERGE INTO FINSIGHT.ACCOUNTS AS target
USING (VALUES ('acc_checking_01', 'usr_demo_synthetic_01', 'Premier Checking', 'CHECKING', 'HDFC Bank', 'INR', 25000.00))
AS src (account_id, user_id, account_name, account_type, institution_name, currency, opening_balance)
ON (target.account_id = src.account_id)
WHEN NOT MATCHED THEN
    INSERT (account_id, user_id, account_name, account_type, institution_name, currency, opening_balance)
    VALUES (src.account_id, src.user_id, src.account_name, src.account_type, src.institution_name, src.currency, src.opening_balance);

MERGE INTO FINSIGHT.ACCOUNTS AS target
USING (VALUES ('acc_savings_01', 'usr_demo_synthetic_01', 'High-Yield Savings', 'SAVINGS', 'ICICI Bank', 'INR', 150000.00))
AS src (account_id, user_id, account_name, account_type, institution_name, currency, opening_balance)
ON (target.account_id = src.account_id)
WHEN NOT MATCHED THEN
    INSERT (account_id, user_id, account_name, account_type, institution_name, currency, opening_balance)
    VALUES (src.account_id, src.user_id, src.account_name, src.account_type, src.institution_name, src.currency, src.opening_balance);

MERGE INTO FINSIGHT.ACCOUNTS AS target
USING (VALUES ('acc_credit_01', 'usr_demo_synthetic_01', 'Millennia Credit Card', 'CREDIT_CARD', 'HDFC Bank', 'INR', 0.00))
AS src (account_id, user_id, account_name, account_type, institution_name, currency, opening_balance)
ON (target.account_id = src.account_id)
WHEN NOT MATCHED THEN
    INSERT (account_id, user_id, account_name, account_type, institution_name, currency, opening_balance)
    VALUES (src.account_id, src.user_id, src.account_name, src.account_type, src.institution_name, src.currency, src.opening_balance);

MERGE INTO FINSIGHT.CATEGORIES AS target
USING (VALUES ('cat_salary', CAST(NULL AS VARCHAR(36)), 'Salary & Wages', 'INCOME'))
AS src (category_id, user_id, category_name, category_type)
ON (target.category_id = src.category_id)
WHEN NOT MATCHED THEN
    INSERT (category_id, user_id, category_name, category_type)
    VALUES (src.category_id, src.user_id, src.category_name, src.category_type);

MERGE INTO FINSIGHT.CATEGORIES AS target
USING (VALUES ('cat_freelance', CAST(NULL AS VARCHAR(36)), 'Consulting & Freelance', 'INCOME'))
AS src (category_id, user_id, category_name, category_type)
ON (target.category_id = src.category_id)
WHEN NOT MATCHED THEN
    INSERT (category_id, user_id, category_name, category_type)
    VALUES (src.category_id, src.user_id, src.category_name, src.category_type);

MERGE INTO FINSIGHT.CATEGORIES AS target
USING (VALUES ('cat_investment', CAST(NULL AS VARCHAR(36)), 'Investment Returns', 'INCOME'))
AS src (category_id, user_id, category_name, category_type)
ON (target.category_id = src.category_id)
WHEN NOT MATCHED THEN
    INSERT (category_id, user_id, category_name, category_type)
    VALUES (src.category_id, src.user_id, src.category_name, src.category_type);

MERGE INTO FINSIGHT.CATEGORIES AS target
USING (VALUES ('cat_groceries', CAST(NULL AS VARCHAR(36)), 'Groceries & Supermarket', 'EXPENSE'))
AS src (category_id, user_id, category_name, category_type)
ON (target.category_id = src.category_id)
WHEN NOT MATCHED THEN
    INSERT (category_id, user_id, category_name, category_type)
    VALUES (src.category_id, src.user_id, src.category_name, src.category_type);

MERGE INTO FINSIGHT.CATEGORIES AS target
USING (VALUES ('cat_dining', CAST(NULL AS VARCHAR(36)), 'Dining & Takeout', 'EXPENSE'))
AS src (category_id, user_id, category_name, category_type)
ON (target.category_id = src.category_id)
WHEN NOT MATCHED THEN
    INSERT (category_id, user_id, category_name, category_type)
    VALUES (src.category_id, src.user_id, src.category_name, src.category_type);

MERGE INTO FINSIGHT.CATEGORIES AS target
USING (VALUES ('cat_utilities', CAST(NULL AS VARCHAR(36)), 'Utilities & Internet', 'EXPENSE'))
AS src (category_id, user_id, category_name, category_type)
ON (target.category_id = src.category_id)
WHEN NOT MATCHED THEN
    INSERT (category_id, user_id, category_name, category_type)
    VALUES (src.category_id, src.user_id, src.category_name, src.category_type);

MERGE INTO FINSIGHT.CATEGORIES AS target
USING (VALUES ('cat_rent', CAST(NULL AS VARCHAR(36)), 'Housing & Rent', 'EXPENSE'))
AS src (category_id, user_id, category_name, category_type)
ON (target.category_id = src.category_id)
WHEN NOT MATCHED THEN
    INSERT (category_id, user_id, category_name, category_type)
    VALUES (src.category_id, src.user_id, src.category_name, src.category_type);

MERGE INTO FINSIGHT.CATEGORIES AS target
USING (VALUES ('cat_subscriptions', CAST(NULL AS VARCHAR(36)), 'Software & Subscriptions', 'EXPENSE'))
AS src (category_id, user_id, category_name, category_type)
ON (target.category_id = src.category_id)
WHEN NOT MATCHED THEN
    INSERT (category_id, user_id, category_name, category_type)
    VALUES (src.category_id, src.user_id, src.category_name, src.category_type);

MERGE INTO FINSIGHT.CATEGORIES AS target
USING (VALUES ('cat_travel', CAST(NULL AS VARCHAR(36)), 'Commute & Travel', 'EXPENSE'))
AS src (category_id, user_id, category_name, category_type)
ON (target.category_id = src.category_id)
WHEN NOT MATCHED THEN
    INSERT (category_id, user_id, category_name, category_type)
    VALUES (src.category_id, src.user_id, src.category_name, src.category_type);

MERGE INTO FINSIGHT.CATEGORIES AS target
USING (VALUES ('cat_shopping', CAST(NULL AS VARCHAR(36)), 'Electronics & Shopping', 'EXPENSE'))
AS src (category_id, user_id, category_name, category_type)
ON (target.category_id = src.category_id)
WHEN NOT MATCHED THEN
    INSERT (category_id, user_id, category_name, category_type)
    VALUES (src.category_id, src.user_id, src.category_name, src.category_type);

MERGE INTO FINSIGHT.CATEGORIES AS target
USING (VALUES ('cat_healthcare', CAST(NULL AS VARCHAR(36)), 'Healthcare & Pharmacy', 'EXPENSE'))
AS src (category_id, user_id, category_name, category_type)
ON (target.category_id = src.category_id)
WHEN NOT MATCHED THEN
    INSERT (category_id, user_id, category_name, category_type)
    VALUES (src.category_id, src.user_id, src.category_name, src.category_type);

MERGE INTO FINSIGHT.CATEGORIES AS target
USING (VALUES ('cat_transfer', CAST(NULL AS VARCHAR(36)), 'Internal Account Transfer', 'TRANSFER'))
AS src (category_id, user_id, category_name, category_type)
ON (target.category_id = src.category_id)
WHEN NOT MATCHED THEN
    INSERT (category_id, user_id, category_name, category_type)
    VALUES (src.category_id, src.user_id, src.category_name, src.category_type);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sal_202606', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_salary', 'SAL-PAYROLL-202606-9821', 'Acme Global Tech Payroll', 'Monthly engineering salary credit', 125000.00, 'INR', 'CREDIT', DATE('2026-06-01'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sav_trf_202606', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_transfer', 'TRF-SAVINGS-202606-4412', 'ICICI Savings Direct', 'Automated monthly emergency fund transfer', 35000.00, 'INR', 'DEBIT', DATE('2026-06-02'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_rent_202606', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_rent', 'UPI-RENT-202606-7723', 'Greenfield Living Properties', 'Monthly apartment rent payment', 32000.00, 'INR', 'DEBIT', DATE('2026-06-05'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_wifi_202606', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_utilities', 'BILL-AIRTEL-202606', 'Airtel Fiber Broadband', 'Gigabit fiber home internet connection', 1199.00, 'INR', 'DEBIT', DATE('2026-06-10'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_elec_202606', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_utilities', 'BILL-BSES-202606', 'BSES Power Distribution', 'Monthly domestic electricity consumption', 2480.00, 'INR', 'DEBIT', DATE('2026-06-12'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_nflx_202606', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-NETFLIX-202606', 'Netflix India', 'Premium 4K Family Plan monthly subscription', 649.00, 'INR', 'DEBIT', DATE('2026-06-15'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_spot_202606', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-SPOTIFY-202606', 'Spotify India', 'Individual Premium Audio streaming', 119.00, 'INR', 'DEBIT', DATE('2026-06-15'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_gh_202606', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-GITHUB-202606', 'GitHub Inc.', 'GitHub Copilot Pro monthly developer plan', 850.00, 'INR', 'DEBIT', DATE('2026-06-16'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_aws_202606', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-AWS-202606', 'Amazon Web Services', 'Cloud hosting development instances', 1420.00, 'INR', 'DEBIT', DATE('2026-06-17'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sal_202607', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_salary', 'SAL-PAYROLL-202607-9821', 'Acme Global Tech Payroll', 'Monthly engineering salary credit', 125000.00, 'INR', 'CREDIT', DATE('2026-07-01'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sav_trf_202607', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_transfer', 'TRF-SAVINGS-202607-4412', 'ICICI Savings Direct', 'Automated monthly emergency fund transfer', 35000.00, 'INR', 'DEBIT', DATE('2026-07-02'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_rent_202607', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_rent', 'UPI-RENT-202607-7723', 'Greenfield Living Properties', 'Monthly apartment rent payment', 32000.00, 'INR', 'DEBIT', DATE('2026-07-05'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_wifi_202607', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_utilities', 'BILL-AIRTEL-202607', 'Airtel Fiber Broadband', 'Gigabit fiber home internet connection', 1199.00, 'INR', 'DEBIT', DATE('2026-07-10'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_elec_202607', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_utilities', 'BILL-BSES-202607', 'BSES Power Distribution', 'Monthly domestic electricity consumption', 2480.00, 'INR', 'DEBIT', DATE('2026-07-12'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_nflx_202607', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-NETFLIX-202607', 'Netflix India', 'Premium 4K Family Plan monthly subscription', 649.00, 'INR', 'DEBIT', DATE('2026-07-15'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_spot_202607', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-SPOTIFY-202607', 'Spotify India', 'Individual Premium Audio streaming', 119.00, 'INR', 'DEBIT', DATE('2026-07-15'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_gh_202607', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-GITHUB-202607', 'GitHub Inc.', 'GitHub Copilot Pro monthly developer plan', 850.00, 'INR', 'DEBIT', DATE('2026-07-16'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_aws_202607', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-AWS-202607', 'Amazon Web Services', 'Cloud hosting development instances', 1420.00, 'INR', 'DEBIT', DATE('2026-07-17'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sal_202608', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_salary', 'SAL-PAYROLL-202608-9821', 'Acme Global Tech Payroll', 'Monthly engineering salary credit', 125000.00, 'INR', 'CREDIT', DATE('2026-08-01'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sav_trf_202608', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_transfer', 'TRF-SAVINGS-202608-4412', 'ICICI Savings Direct', 'Automated monthly emergency fund transfer', 35000.00, 'INR', 'DEBIT', DATE('2026-08-02'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_rent_202608', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_rent', 'UPI-RENT-202608-7723', 'Greenfield Living Properties', 'Monthly apartment rent payment', 32000.00, 'INR', 'DEBIT', DATE('2026-08-05'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_wifi_202608', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_utilities', 'BILL-AIRTEL-202608', 'Airtel Fiber Broadband', 'Gigabit fiber home internet connection', 1199.00, 'INR', 'DEBIT', DATE('2026-08-10'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_elec_202608', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_utilities', 'BILL-BSES-202608', 'BSES Power Distribution', 'Monthly domestic electricity consumption', 2480.00, 'INR', 'DEBIT', DATE('2026-08-12'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_nflx_202608', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-NETFLIX-202608', 'Netflix India', 'Premium 4K Family Plan monthly subscription', 649.00, 'INR', 'DEBIT', DATE('2026-08-15'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_spot_202608', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-SPOTIFY-202608', 'Spotify India', 'Individual Premium Audio streaming', 119.00, 'INR', 'DEBIT', DATE('2026-08-15'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_gh_202608', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-GITHUB-202608', 'GitHub Inc.', 'GitHub Copilot Pro monthly developer plan', 850.00, 'INR', 'DEBIT', DATE('2026-08-16'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_aws_202608', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-AWS-202608', 'Amazon Web Services', 'Cloud hosting development instances', 1420.00, 'INR', 'DEBIT', DATE('2026-08-17'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sal_202609', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_salary', 'SAL-PAYROLL-202609-9821', 'Acme Global Tech Payroll', 'Monthly engineering salary credit', 125000.00, 'INR', 'CREDIT', DATE('2026-09-01'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sav_trf_202609', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_transfer', 'TRF-SAVINGS-202609-4412', 'ICICI Savings Direct', 'Automated monthly emergency fund transfer', 35000.00, 'INR', 'DEBIT', DATE('2026-09-02'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_rent_202609', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_rent', 'UPI-RENT-202609-7723', 'Greenfield Living Properties', 'Monthly apartment rent payment', 32000.00, 'INR', 'DEBIT', DATE('2026-09-05'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_wifi_202609', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_utilities', 'BILL-AIRTEL-202609', 'Airtel Fiber Broadband', 'Gigabit fiber home internet connection', 1199.00, 'INR', 'DEBIT', DATE('2026-09-10'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_elec_202609', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_utilities', 'BILL-BSES-202609', 'BSES Power Distribution', 'Monthly domestic electricity consumption', 2480.00, 'INR', 'DEBIT', DATE('2026-09-12'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_nflx_202609', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-NETFLIX-202609', 'Netflix India', 'Premium 4K Family Plan monthly subscription', 649.00, 'INR', 'DEBIT', DATE('2026-09-15'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_spot_202609', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-SPOTIFY-202609', 'Spotify India', 'Individual Premium Audio streaming', 119.00, 'INR', 'DEBIT', DATE('2026-09-15'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_gh_202609', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-GITHUB-202609', 'GitHub Inc.', 'GitHub Copilot Pro monthly developer plan', 850.00, 'INR', 'DEBIT', DATE('2026-09-16'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_aws_202609', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-AWS-202609', 'Amazon Web Services', 'Cloud hosting development instances', 1420.00, 'INR', 'DEBIT', DATE('2026-09-17'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sal_202610', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_salary', 'SAL-PAYROLL-202610-9821', 'Acme Global Tech Payroll', 'Monthly engineering salary credit', 125000.00, 'INR', 'CREDIT', DATE('2026-10-01'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sav_trf_202610', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_transfer', 'TRF-SAVINGS-202610-4412', 'ICICI Savings Direct', 'Automated monthly emergency fund transfer', 35000.00, 'INR', 'DEBIT', DATE('2026-10-02'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_rent_202610', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_rent', 'UPI-RENT-202610-7723', 'Greenfield Living Properties', 'Monthly apartment rent payment', 32000.00, 'INR', 'DEBIT', DATE('2026-10-05'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_wifi_202610', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_utilities', 'BILL-AIRTEL-202610', 'Airtel Fiber Broadband', 'Gigabit fiber home internet connection', 1199.00, 'INR', 'DEBIT', DATE('2026-10-10'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_elec_202610', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_utilities', 'BILL-BSES-202610', 'BSES Power Distribution', 'Monthly domestic electricity consumption', 2480.00, 'INR', 'DEBIT', DATE('2026-10-12'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_nflx_202610', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-NETFLIX-202610', 'Netflix India', 'Premium 4K Family Plan monthly subscription', 649.00, 'INR', 'DEBIT', DATE('2026-10-15'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_spot_202610', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-SPOTIFY-202610', 'Spotify India', 'Individual Premium Audio streaming', 119.00, 'INR', 'DEBIT', DATE('2026-10-15'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_gh_202610', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-GITHUB-202610', 'GitHub Inc.', 'GitHub Copilot Pro monthly developer plan', 850.00, 'INR', 'DEBIT', DATE('2026-10-16'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_aws_202610', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-AWS-202610', 'Amazon Web Services', 'Cloud hosting development instances', 1420.00, 'INR', 'DEBIT', DATE('2026-10-17'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sal_202611', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_salary', 'SAL-PAYROLL-202611-9821', 'Acme Global Tech Payroll', 'Monthly engineering salary credit', 125000.00, 'INR', 'CREDIT', DATE('2026-11-01'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sav_trf_202611', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_transfer', 'TRF-SAVINGS-202611-4412', 'ICICI Savings Direct', 'Automated monthly emergency fund transfer', 35000.00, 'INR', 'DEBIT', DATE('2026-11-02'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_rent_202611', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_rent', 'UPI-RENT-202611-7723', 'Greenfield Living Properties', 'Monthly apartment rent payment', 32000.00, 'INR', 'DEBIT', DATE('2026-11-05'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_wifi_202611', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_utilities', 'BILL-AIRTEL-202611', 'Airtel Fiber Broadband', 'Gigabit fiber home internet connection', 1199.00, 'INR', 'DEBIT', DATE('2026-11-10'), 'PENDING', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_elec_202611', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_utilities', 'BILL-BSES-202611', 'BSES Power Distribution', 'Monthly domestic electricity consumption', 2480.00, 'INR', 'DEBIT', DATE('2026-11-12'), 'PENDING', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_nflx_202611', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-NETFLIX-202611', 'Netflix India', 'Premium 4K Family Plan monthly subscription', 649.00, 'INR', 'DEBIT', DATE('2026-11-15'), 'PENDING', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_spot_202611', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-SPOTIFY-202611', 'Spotify India', 'Individual Premium Audio streaming', 119.00, 'INR', 'DEBIT', DATE('2026-11-15'), 'PENDING', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_gh_202611', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-GITHUB-202611', 'GitHub Inc.', 'GitHub Copilot Pro monthly developer plan', 850.00, 'INR', 'DEBIT', DATE('2026-11-16'), 'PENDING', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_sub_aws_202611', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-AWS-202611', 'Amazon Web Services', 'Cloud hosting development instances', 1420.00, 'INR', 'DEBIT', DATE('2026-11-17'), 'PENDING', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260601_0', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260601-0', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-06-01'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260603_2', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260603-2', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-06-03'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260604_3', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260604-3', 'BigBasket Organic', 'Monthly household cleaning & dry provisions', 2490.00, 'INR', 'DEBIT', DATE('2026-06-04'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260605_4', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260605-4', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-06-05'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260606_5', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260606-5', 'Starbucks Coffee', 'Caffe latte and roasted bagel', 580.00, 'INR', 'DEBIT', DATE('2026-06-06'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260607_6', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260607-6', 'Swiggy Gourmet', 'Dinner delivery from Burma Burma', 1250.00, 'INR', 'DEBIT', DATE('2026-06-07'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260608_7', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260608-7', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-06-08'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260608_7', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260608-7', 'BigBasket Organic', 'Monthly household cleaning & dry provisions', 2490.00, 'INR', 'DEBIT', DATE('2026-06-08'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260610_9', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260610-9', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-06-10'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260612_11', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260612-11', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-06-12'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260612_11', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260612-11', 'BigBasket Organic', 'Monthly household cleaning & dry provisions', 2490.00, 'INR', 'DEBIT', DATE('2026-06-12'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260613_12', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260613-12', 'Blue Tokai Coffee Roasters', 'Cold brew and almond croissant', 420.00, 'INR', 'DEBIT', DATE('2026-06-13'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260614_13', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260614-13', 'Starbucks Coffee', 'Caffe latte and roasted bagel', 580.00, 'INR', 'DEBIT', DATE('2026-06-14'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260615_14', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260615-14', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-06-15'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260616_15', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260616-15', 'BigBasket Organic', 'Monthly household cleaning & dry provisions', 2490.00, 'INR', 'DEBIT', DATE('2026-06-16'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260617_16', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260617-16', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-06-17'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260619_18', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260619-18', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-06-19'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260620_19', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260620-19', 'BigBasket Organic', 'Monthly household cleaning & dry provisions', 2490.00, 'INR', 'DEBIT', DATE('2026-06-20'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260620_19', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260620-19', 'Zomato Delivery', 'Woodfired sourdough pizza and salad', 890.00, 'INR', 'DEBIT', DATE('2026-06-20'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260621_20', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260621-20', 'Blue Tokai Coffee Roasters', 'Cold brew and almond croissant', 420.00, 'INR', 'DEBIT', DATE('2026-06-21'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260622_21', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260622-21', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-06-22'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260624_23', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260624-23', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-06-24'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260624_23', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260624-23', 'BigBasket Organic', 'Monthly household cleaning & dry provisions', 2490.00, 'INR', 'DEBIT', DATE('2026-06-24'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260626_25', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260626-25', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-06-26'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260627_26', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260627-26', 'Swiggy Gourmet', 'Dinner delivery from Burma Burma', 1250.00, 'INR', 'DEBIT', DATE('2026-06-27'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260628_27', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260628-27', 'BigBasket Organic', 'Monthly household cleaning & dry provisions', 2490.00, 'INR', 'DEBIT', DATE('2026-06-28'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260628_27', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260628-27', 'Zomato Delivery', 'Woodfired sourdough pizza and salad', 890.00, 'INR', 'DEBIT', DATE('2026-06-28'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260629_28', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260629-28', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-06-29'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260701_30', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260701-30', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-07-01'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260703_32', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260703-32', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-07-03'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260704_33', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260704-33', 'Zepto Quick Commerce', 'Fresh vegetables and sourdough bread', 820.00, 'INR', 'DEBIT', DATE('2026-07-04'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260704_33', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260704-33', 'Starbucks Coffee', 'Caffe latte and roasted bagel', 580.00, 'INR', 'DEBIT', DATE('2026-07-04'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260705_34', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260705-34', 'Swiggy Gourmet', 'Dinner delivery from Burma Burma', 1250.00, 'INR', 'DEBIT', DATE('2026-07-05'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260706_35', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260706-35', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-07-06'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260708_37', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260708-37', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-07-08'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260708_37', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260708-37', 'Zepto Quick Commerce', 'Fresh vegetables and sourdough bread', 820.00, 'INR', 'DEBIT', DATE('2026-07-08'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260710_39', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260710-39', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-07-10'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260711_40', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260711-40', 'Blue Tokai Coffee Roasters', 'Cold brew and almond croissant', 420.00, 'INR', 'DEBIT', DATE('2026-07-11'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260712_41', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260712-41', 'Zepto Quick Commerce', 'Fresh vegetables and sourdough bread', 820.00, 'INR', 'DEBIT', DATE('2026-07-12'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260712_41', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260712-41', 'Starbucks Coffee', 'Caffe latte and roasted bagel', 580.00, 'INR', 'DEBIT', DATE('2026-07-12'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260713_42', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260713-42', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-07-13'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260715_44', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260715-44', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-07-15'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260716_45', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260716-45', 'Zepto Quick Commerce', 'Fresh vegetables and sourdough bread', 820.00, 'INR', 'DEBIT', DATE('2026-07-16'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260717_46', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260717-46', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-07-17'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260718_47', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260718-47', 'Zomato Delivery', 'Woodfired sourdough pizza and salad', 890.00, 'INR', 'DEBIT', DATE('2026-07-18'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260719_48', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260719-48', 'Blue Tokai Coffee Roasters', 'Cold brew and almond croissant', 420.00, 'INR', 'DEBIT', DATE('2026-07-19'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260720_49', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260720-49', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-07-20'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260720_49', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260720-49', 'Zepto Quick Commerce', 'Fresh vegetables and sourdough bread', 820.00, 'INR', 'DEBIT', DATE('2026-07-20'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260722_51', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260722-51', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-07-22'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260724_53', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260724-53', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-07-24'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260724_53', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260724-53', 'Zepto Quick Commerce', 'Fresh vegetables and sourdough bread', 820.00, 'INR', 'DEBIT', DATE('2026-07-24'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260725_54', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260725-54', 'Swiggy Gourmet', 'Dinner delivery from Burma Burma', 1250.00, 'INR', 'DEBIT', DATE('2026-07-25'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260726_55', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260726-55', 'Zomato Delivery', 'Woodfired sourdough pizza and salad', 890.00, 'INR', 'DEBIT', DATE('2026-07-26'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260727_56', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260727-56', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-07-27'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260728_57', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260728-57', 'Zepto Quick Commerce', 'Fresh vegetables and sourdough bread', 820.00, 'INR', 'DEBIT', DATE('2026-07-28'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260729_58', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260729-58', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-07-29'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260731_60', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260731-60', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-07-31'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260801_61', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260801-61', 'Starbucks Coffee', 'Caffe latte and roasted bagel', 580.00, 'INR', 'DEBIT', DATE('2026-08-01'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260802_62', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260802-62', 'Swiggy Gourmet', 'Dinner delivery from Burma Burma', 1250.00, 'INR', 'DEBIT', DATE('2026-08-02'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260803_63', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260803-63', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-08-03'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260804_64', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260804-64', 'Blinkit Express', 'Weekly groceries and dairy staples', 1340.00, 'INR', 'DEBIT', DATE('2026-08-04'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260805_65', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260805-65', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-08-05'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260807_67', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260807-67', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-08-07'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260808_68', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260808-68', 'Blinkit Express', 'Weekly groceries and dairy staples', 1340.00, 'INR', 'DEBIT', DATE('2026-08-08'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260808_68', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260808-68', 'Blue Tokai Coffee Roasters', 'Cold brew and almond croissant', 420.00, 'INR', 'DEBIT', DATE('2026-08-08'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260809_69', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260809-69', 'Starbucks Coffee', 'Caffe latte and roasted bagel', 580.00, 'INR', 'DEBIT', DATE('2026-08-09'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260810_70', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260810-70', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-08-10'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260812_72', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260812-72', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-08-12'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260812_72', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260812-72', 'Blinkit Express', 'Weekly groceries and dairy staples', 1340.00, 'INR', 'DEBIT', DATE('2026-08-12'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260814_74', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260814-74', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-08-14'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260815_75', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260815-75', 'Zomato Delivery', 'Woodfired sourdough pizza and salad', 890.00, 'INR', 'DEBIT', DATE('2026-08-15'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260816_76', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260816-76', 'Blinkit Express', 'Weekly groceries and dairy staples', 1340.00, 'INR', 'DEBIT', DATE('2026-08-16'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260816_76', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260816-76', 'Blue Tokai Coffee Roasters', 'Cold brew and almond croissant', 420.00, 'INR', 'DEBIT', DATE('2026-08-16'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260817_77', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260817-77', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-08-17'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260819_79', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260819-79', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-08-19'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260820_80', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260820-80', 'Blinkit Express', 'Weekly groceries and dairy staples', 1340.00, 'INR', 'DEBIT', DATE('2026-08-20'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260821_81', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260821-81', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-08-21'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260822_82', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260822-82', 'Swiggy Gourmet', 'Dinner delivery from Burma Burma', 1250.00, 'INR', 'DEBIT', DATE('2026-08-22'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260823_83', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260823-83', 'Zomato Delivery', 'Woodfired sourdough pizza and salad', 890.00, 'INR', 'DEBIT', DATE('2026-08-23'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260824_84', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260824-84', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-08-24'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260824_84', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260824-84', 'Blinkit Express', 'Weekly groceries and dairy staples', 1340.00, 'INR', 'DEBIT', DATE('2026-08-24'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260826_86', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260826-86', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-08-26'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260828_88', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260828-88', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-08-28'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260828_88', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260828-88', 'Blinkit Express', 'Weekly groceries and dairy staples', 1340.00, 'INR', 'DEBIT', DATE('2026-08-28'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260829_89', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260829-89', 'Starbucks Coffee', 'Caffe latte and roasted bagel', 580.00, 'INR', 'DEBIT', DATE('2026-08-29'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260830_90', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260830-90', 'Swiggy Gourmet', 'Dinner delivery from Burma Burma', 1250.00, 'INR', 'DEBIT', DATE('2026-08-30'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260831_91', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260831-91', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-08-31'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260902_93', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260902-93', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-09-02'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260904_95', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260904-95', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-09-04'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260904_95', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260904-95', 'BigBasket Organic', 'Monthly household cleaning & dry provisions', 2490.00, 'INR', 'DEBIT', DATE('2026-09-04'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260905_96', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260905-96', 'Blue Tokai Coffee Roasters', 'Cold brew and almond croissant', 420.00, 'INR', 'DEBIT', DATE('2026-09-05'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260906_97', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260906-97', 'Starbucks Coffee', 'Caffe latte and roasted bagel', 580.00, 'INR', 'DEBIT', DATE('2026-09-06'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260907_98', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260907-98', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-09-07'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260908_99', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260908-99', 'BigBasket Organic', 'Monthly household cleaning & dry provisions', 2490.00, 'INR', 'DEBIT', DATE('2026-09-08'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260909_100', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260909-100', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-09-09'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260911_102', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260911-102', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-09-11'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260912_103', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260912-103', 'BigBasket Organic', 'Monthly household cleaning & dry provisions', 2490.00, 'INR', 'DEBIT', DATE('2026-09-12'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260912_103', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260912-103', 'Zomato Delivery', 'Woodfired sourdough pizza and salad', 890.00, 'INR', 'DEBIT', DATE('2026-09-12'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260913_104', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260913-104', 'Blue Tokai Coffee Roasters', 'Cold brew and almond croissant', 420.00, 'INR', 'DEBIT', DATE('2026-09-13'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260914_105', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260914-105', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-09-14'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260916_107', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260916-107', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-09-16'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260916_107', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260916-107', 'BigBasket Organic', 'Monthly household cleaning & dry provisions', 2490.00, 'INR', 'DEBIT', DATE('2026-09-16'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260918_109', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260918-109', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-09-18'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260919_110', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260919-110', 'Swiggy Gourmet', 'Dinner delivery from Burma Burma', 1250.00, 'INR', 'DEBIT', DATE('2026-09-19'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260920_111', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260920-111', 'BigBasket Organic', 'Monthly household cleaning & dry provisions', 2490.00, 'INR', 'DEBIT', DATE('2026-09-20'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260920_111', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260920-111', 'Zomato Delivery', 'Woodfired sourdough pizza and salad', 890.00, 'INR', 'DEBIT', DATE('2026-09-20'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260921_112', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260921-112', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-09-21'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260923_114', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260923-114', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-09-23'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260924_115', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260924-115', 'BigBasket Organic', 'Monthly household cleaning & dry provisions', 2490.00, 'INR', 'DEBIT', DATE('2026-09-24'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260925_116', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260925-116', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-09-25'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260926_117', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260926-117', 'Starbucks Coffee', 'Caffe latte and roasted bagel', 580.00, 'INR', 'DEBIT', DATE('2026-09-26'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20260927_118', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20260927-118', 'Swiggy Gourmet', 'Dinner delivery from Burma Burma', 1250.00, 'INR', 'DEBIT', DATE('2026-09-27'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260928_119', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260928-119', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-09-28'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20260928_119', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20260928-119', 'BigBasket Organic', 'Monthly household cleaning & dry provisions', 2490.00, 'INR', 'DEBIT', DATE('2026-09-28'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20260930_121', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20260930-121', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-09-30'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20261002_123', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20261002-123', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-10-02'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20261003_124', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20261003-124', 'Blue Tokai Coffee Roasters', 'Cold brew and almond croissant', 420.00, 'INR', 'DEBIT', DATE('2026-10-03'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20261004_125', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20261004-125', 'Zepto Quick Commerce', 'Fresh vegetables and sourdough bread', 820.00, 'INR', 'DEBIT', DATE('2026-10-04'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20261004_125', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20261004-125', 'Starbucks Coffee', 'Caffe latte and roasted bagel', 580.00, 'INR', 'DEBIT', DATE('2026-10-04'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20261005_126', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20261005-126', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-10-05'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20261007_128', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20261007-128', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-10-07'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20261008_129', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20261008-129', 'Zepto Quick Commerce', 'Fresh vegetables and sourdough bread', 820.00, 'INR', 'DEBIT', DATE('2026-10-08'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20261009_130', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20261009-130', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-10-09'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20261010_131', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20261010-131', 'Zomato Delivery', 'Woodfired sourdough pizza and salad', 890.00, 'INR', 'DEBIT', DATE('2026-10-10'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20261011_132', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20261011-132', 'Blue Tokai Coffee Roasters', 'Cold brew and almond croissant', 420.00, 'INR', 'DEBIT', DATE('2026-10-11'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20261012_133', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20261012-133', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-10-12'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20261012_133', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20261012-133', 'Zepto Quick Commerce', 'Fresh vegetables and sourdough bread', 820.00, 'INR', 'DEBIT', DATE('2026-10-12'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20261014_135', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20261014-135', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-10-14'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20261016_137', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20261016-137', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-10-16'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20261016_137', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20261016-137', 'Zepto Quick Commerce', 'Fresh vegetables and sourdough bread', 820.00, 'INR', 'DEBIT', DATE('2026-10-16'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20261017_138', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20261017-138', 'Swiggy Gourmet', 'Dinner delivery from Burma Burma', 1250.00, 'INR', 'DEBIT', DATE('2026-10-17'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20261018_139', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20261018-139', 'Zomato Delivery', 'Woodfired sourdough pizza and salad', 890.00, 'INR', 'DEBIT', DATE('2026-10-18'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20261019_140', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20261019-140', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-10-19'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20261020_141', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20261020-141', 'Zepto Quick Commerce', 'Fresh vegetables and sourdough bread', 820.00, 'INR', 'DEBIT', DATE('2026-10-20'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20261021_142', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20261021-142', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-10-21'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20261023_144', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20261023-144', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-10-23'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20261024_145', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20261024-145', 'Zepto Quick Commerce', 'Fresh vegetables and sourdough bread', 820.00, 'INR', 'DEBIT', DATE('2026-10-24'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20261024_145', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20261024-145', 'Starbucks Coffee', 'Caffe latte and roasted bagel', 580.00, 'INR', 'DEBIT', DATE('2026-10-24'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20261025_146', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20261025-146', 'Swiggy Gourmet', 'Dinner delivery from Burma Burma', 1250.00, 'INR', 'DEBIT', DATE('2026-10-25'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20261026_147', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20261026-147', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-10-26'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20261028_149', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20261028-149', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-10-28'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20261028_149', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20261028-149', 'Zepto Quick Commerce', 'Fresh vegetables and sourdough bread', 820.00, 'INR', 'DEBIT', DATE('2026-10-28'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20261030_151', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20261030-151', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-10-30'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20261031_152', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20261031-152', 'Blue Tokai Coffee Roasters', 'Cold brew and almond croissant', 420.00, 'INR', 'DEBIT', DATE('2026-10-31'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_dine_20261101_153', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_dining', 'POS-DINE-20261101-153', 'Starbucks Coffee', 'Caffe latte and roasted bagel', 580.00, 'INR', 'DEBIT', DATE('2026-11-01'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20261102_154', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20261102-154', 'Uber India', 'Afternoon return cab from client meeting', 360.00, 'INR', 'DEBIT', DATE('2026-11-02'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20261104_156', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20261104-156', 'Uber India', 'Premier cab to tech innovation campus', 480.00, 'INR', 'DEBIT', DATE('2026-11-04'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_groc_20261104_156', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_groceries', 'UPI-GROC-20261104-156', 'Blinkit Express', 'Weekly groceries and dairy staples', 1340.00, 'INR', 'DEBIT', DATE('2026-11-04'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_comm_20261106_158', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_travel', 'RIDE-20261106-158', 'Ola Cabs', 'Cab ride to metro interchange', 290.00, 'INR', 'DEBIT', DATE('2026-11-06'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_anom_01_luxury_spike', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_shopping', 'TXN-INTR-901844', 'Luxury Electronics Dubai FZE', 'High-ticket foreign transaction for mirrorless cinema camera', 84500.00, 'INR', 'DEBIT', DATE('2026-09-18'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_anom_02_velocity_1', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_shopping', 'FASTPAY-GW-110291', 'FastPay Cash Gateway', 'Unusual high-speed payout test charge 1 of 3', 9999.00, 'INR', 'DEBIT', DATE('2026-10-04'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_anom_02_velocity_2', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_shopping', 'FASTPAY-GW-110292', 'FastPay Cash Gateway', 'Unusual high-speed payout test charge 2 of 3', 9999.00, 'INR', 'DEBIT', DATE('2026-10-04'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_anom_02_velocity_3', 'usr_demo_synthetic_01', 'acc_checking_01', 'cat_shopping', 'FASTPAY-GW-110293', 'FastPay Cash Gateway', 'Unusual high-speed payout test charge 3 of 3', 9999.00, 'INR', 'DEBIT', DATE('2026-10-04'), 'POSTED', 'BANK_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('tx_anom_03_subscription_jump', 'usr_demo_synthetic_01', 'acc_credit_01', 'cat_subscriptions', 'SUB-AWS-SPIKE-1028', 'Amazon Web Services', 'Unexpected 30x cost drift spike due to runaway GPU instance cluster', 42800.00, 'INR', 'DEBIT', DATE('2026-10-28'), 'POSTED', 'CREDIT_CARD_SYNC'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);

MERGE INTO FINSIGHT.ANOMALY_ALERTS AS target
USING (VALUES ('alt_01', 'usr_demo_synthetic_01', 'tx_anom_01_luxury_spike', 'AMOUNT_SPIKE', 'HIGH', 'Single transaction of INR 84,500.00 is 14.8x standard deviation above the 90-day shopping average (INR 2,850.00). Unfamiliar foreign merchant detected.', 94.50, 'ACTIVE'))
AS src (alert_id, user_id, transaction_id, alert_type, severity, explanation, score, status)
ON (target.alert_id = src.alert_id)
WHEN NOT MATCHED THEN
    INSERT (alert_id, user_id, transaction_id, alert_type, severity, explanation, score, status)
    VALUES (src.alert_id, src.user_id, src.transaction_id, src.alert_type, src.severity, src.explanation, src.score, src.status);

MERGE INTO FINSIGHT.ANOMALY_ALERTS AS target
USING (VALUES ('alt_02', 'usr_demo_synthetic_01', 'tx_anom_02_velocity_1', 'VELOCITY_SPIKE', 'CRITICAL', 'Rapid velocity burst: 3 consecutive transactions of INR 9,999.00 executed within 10 minutes against payment gateway ''FastPay Cash Gateway''.', 98.20, 'ACTIVE'))
AS src (alert_id, user_id, transaction_id, alert_type, severity, explanation, score, status)
ON (target.alert_id = src.alert_id)
WHEN NOT MATCHED THEN
    INSERT (alert_id, user_id, transaction_id, alert_type, severity, explanation, score, status)
    VALUES (src.alert_id, src.user_id, src.transaction_id, src.alert_type, src.severity, src.explanation, src.score, src.status);

MERGE INTO FINSIGHT.ANOMALY_ALERTS AS target
USING (VALUES ('alt_03', 'usr_demo_synthetic_01', 'tx_anom_03_subscription_jump', 'RECURRING_DRIFT', 'HIGH', 'Recurring software cost drift: Amazon Web Services billed INR 42,800.00, representing a 3,014% surge compared to historic monthly baseline of INR 1,420.00.', 91.00, 'ACTIVE'))
AS src (alert_id, user_id, transaction_id, alert_type, severity, explanation, score, status)
ON (target.alert_id = src.alert_id)
WHEN NOT MATCHED THEN
    INSERT (alert_id, user_id, transaction_id, alert_type, severity, explanation, score, status)
    VALUES (src.alert_id, src.user_id, src.transaction_id, src.alert_type, src.severity, src.explanation, src.score, src.status);
