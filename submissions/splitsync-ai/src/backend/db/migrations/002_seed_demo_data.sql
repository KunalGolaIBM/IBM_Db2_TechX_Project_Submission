-- Demo Seed Data Migration for SplitSync AI
-- 1. Demo Users (Password for all: Password123!)
INSERT INTO APP_USERS (USER_ID, DISPLAY_NAME, EMAIL, PASSWORD_HASH, STATUS)
VALUES ('user-arjun-001', 'Arjun Sharma', 'arjun@example.com', '$2b$12$QDy63SqQLqivOBmp1luyd.UAxLU1etws7QQo01Egic2qgmguL8sZ.', 'ACTIVE');

INSERT INTO APP_USERS (USER_ID, DISPLAY_NAME, EMAIL, PASSWORD_HASH, STATUS)
VALUES ('user-priya-002', 'Priya Patel', 'priya@example.com', '$2b$12$QDy63SqQLqivOBmp1luyd.UAxLU1etws7QQo01Egic2qgmguL8sZ.', 'ACTIVE');

INSERT INTO APP_USERS (USER_ID, DISPLAY_NAME, EMAIL, PASSWORD_HASH, STATUS)
VALUES ('user-rohan-003', 'Rohan Verma', 'rohan@example.com', '$2b$12$QDy63SqQLqivOBmp1luyd.UAxLU1etws7QQo01Egic2qgmguL8sZ.', 'ACTIVE');

-- 2. Demo Group
INSERT INTO GROUPS (GROUP_ID, NAME, DESCRIPTION, CURRENCY, SPLIT_METHOD, ACCOUNTING_MODE, STATUS, CREATED_BY)
VALUES ('group-goa-2026', 'Goa Trip 2026', 'Friends weekend getaway to South Goa', 'INR', 'EQUAL', 'DIRECT', 'ACTIVE', 'user-arjun-001');

-- 3. Demo Group Members
INSERT INTO GROUP_MEMBERS (GROUP_MEMBER_ID, GROUP_ID, USER_ID, ROLE, STATUS)
VALUES ('member-arjun-001', 'group-goa-2026', 'user-arjun-001', 'ADMIN', 'ACTIVE');

INSERT INTO GROUP_MEMBERS (GROUP_MEMBER_ID, GROUP_ID, USER_ID, ROLE, STATUS)
VALUES ('member-priya-002', 'group-goa-2026', 'user-priya-002', 'MEMBER', 'ACTIVE');

INSERT INTO GROUP_MEMBERS (GROUP_MEMBER_ID, GROUP_ID, USER_ID, ROLE, STATUS)
VALUES ('member-rohan-003', 'group-goa-2026', 'user-rohan-003', 'MEMBER', 'ACTIVE');

-- 4. Demo Digital Payment (Arjun contributed ₹3,000 via Demo QR)
INSERT INTO PAYMENT_EVENTS (PAYMENT_ID, GROUP_ID, MEMBER_ID, PROVIDER, PROVIDER_TXN_ID, AMOUNT_MINOR, CURRENCY, STATUS, SOURCE, IDEMPOTENCY_KEY)
VALUES ('pay-demo-001', 'group-goa-2026', 'member-arjun-001', 'DEMO', 'DEMO-TXN-1001', 300000, 'INR', 'VERIFIED', 'DEMO', 'IDEMP-DEMO-PAY-001');

-- 5. Demo Cash Contribution (Priya submitted ₹1,500 cash, approved)
INSERT INTO CASH_CONTRIBUTIONS (CASH_CONTRIBUTION_ID, GROUP_ID, MEMBER_ID, AMOUNT_MINOR, DESCRIPTION, STATUS)
VALUES ('cash-demo-001', 'group-goa-2026', 'member-priya-002', 150000, 'Cash given for resort snacks', 'APPROVED');

-- 6. Demo Cash Approval Record
INSERT INTO CASH_APPROVALS (APPROVAL_ID, ENTITY_TYPE, ENTITY_ID, APPROVER_MEMBER_ID, DECISION, COMMENT)
VALUES ('appr-demo-001', 'CASH_CONTRIBUTION', 'cash-demo-001', 'member-arjun-001', 'APPROVED', 'Received cash by hand');

-- 7. Demo Expense (Beach Resort Stay ₹3,000 paid by Arjun, split equally among 3)
INSERT INTO EXPENSES (EXPENSE_ID, GROUP_ID, PAID_BY_MEMBER_ID, AMOUNT_MINOR, DESCRIPTION, CATEGORY, PAYMENT_METHOD, STATUS)
VALUES ('exp-demo-001', 'group-goa-2026', 'member-arjun-001', 300000, 'Beach Resort Cottage Booking', 'Accommodation', 'DIGITAL', 'VERIFIED');

-- 8. Expense Splits (₹1,000 each = 100000 paise)
INSERT INTO EXPENSE_SPLITS (SPLIT_ID, EXPENSE_ID, MEMBER_ID, SHARE_MINOR)
VALUES ('split-demo-001', 'exp-demo-001', 'member-arjun-001', 100000);

INSERT INTO EXPENSE_SPLITS (SPLIT_ID, EXPENSE_ID, MEMBER_ID, SHARE_MINOR)
VALUES ('split-demo-002', 'exp-demo-001', 'member-priya-002', 100000);

INSERT INTO EXPENSE_SPLITS (SPLIT_ID, EXPENSE_ID, MEMBER_ID, SHARE_MINOR)
VALUES ('split-demo-003', 'exp-demo-001', 'member-rohan-003', 100000);

-- 9. Ledger Entries for Accurate Balancing
-- Arjun payment credit
INSERT INTO LEDGER_ENTRIES (LEDGER_ENTRY_ID, GROUP_ID, MEMBER_ID, ENTITY_TYPE, ENTITY_ID, ENTRY_TYPE, AMOUNT_MINOR, CURRENCY, STATUS)
VALUES ('led-demo-001', 'group-goa-2026', 'member-arjun-001', 'PAYMENT', 'pay-demo-001', 'CREDIT', 300000, 'INR', 'POSTED');

-- Priya approved cash credit
INSERT INTO LEDGER_ENTRIES (LEDGER_ENTRY_ID, GROUP_ID, MEMBER_ID, ENTITY_TYPE, ENTITY_ID, ENTRY_TYPE, AMOUNT_MINOR, CURRENCY, STATUS)
VALUES ('led-demo-002', 'group-goa-2026', 'member-priya-002', 'CASH_CONTRIBUTION', 'cash-demo-001', 'CREDIT', 150000, 'INR', 'POSTED');

-- Arjun paid expense credit
INSERT INTO LEDGER_ENTRIES (LEDGER_ENTRY_ID, GROUP_ID, MEMBER_ID, ENTITY_TYPE, ENTITY_ID, ENTRY_TYPE, AMOUNT_MINOR, CURRENCY, STATUS)
VALUES ('led-demo-003', 'group-goa-2026', 'member-arjun-001', 'EXPENSE', 'exp-demo-001', 'CREDIT', 300000, 'INR', 'POSTED');

-- Participant share debits
INSERT INTO LEDGER_ENTRIES (LEDGER_ENTRY_ID, GROUP_ID, MEMBER_ID, ENTITY_TYPE, ENTITY_ID, ENTRY_TYPE, AMOUNT_MINOR, CURRENCY, STATUS)
VALUES ('led-demo-004', 'group-goa-2026', 'member-arjun-001', 'EXPENSE_SPLIT', 'split-demo-001', 'DEBIT', 100000, 'INR', 'POSTED');

INSERT INTO LEDGER_ENTRIES (LEDGER_ENTRY_ID, GROUP_ID, MEMBER_ID, ENTITY_TYPE, ENTITY_ID, ENTRY_TYPE, AMOUNT_MINOR, CURRENCY, STATUS)
VALUES ('led-demo-005', 'group-goa-2026', 'member-priya-002', 'EXPENSE_SPLIT', 'split-demo-002', 'DEBIT', 100000, 'INR', 'POSTED');

INSERT INTO LEDGER_ENTRIES (LEDGER_ENTRY_ID, GROUP_ID, MEMBER_ID, ENTITY_TYPE, ENTITY_ID, ENTRY_TYPE, AMOUNT_MINOR, CURRENCY, STATUS)
VALUES ('led-demo-006', 'group-goa-2026', 'member-rohan-003', 'EXPENSE_SPLIT', 'split-demo-003', 'DEBIT', 100000, 'INR', 'POSTED');
