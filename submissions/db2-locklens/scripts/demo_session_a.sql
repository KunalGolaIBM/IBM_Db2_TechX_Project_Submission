-- SESSION A (the blocker). Run with autocommit OFF (+c) in the first terminal:
--     db2 connect to testdb
--     db2 +c -tvf demo_session_a.sql
-- It updates row 1 and then deliberately does NOT commit. Leave the terminal open.
-- When you are done: `db2 commit` or `db2 rollback` in this same terminal.
UPDATE LOCKLENS_DEMO.ACCOUNTS SET BALANCE = BALANCE - 100 WHERE ID = 1;
-- intentionally no COMMIT here
