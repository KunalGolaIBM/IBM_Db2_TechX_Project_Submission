-- SESSION B (the waiter). Run in a SECOND terminal, with its own connection:
--     db2 connect to testdb
--     db2 -tvf demo_session_b.sql
-- The UPDATE below targets the same row Session A has locked, so this command waits.
-- It must be an UPDATE: readers may skip the lock under Db2's CUR_COMMIT default.
SET CURRENT LOCK TIMEOUT 300;
UPDATE LOCKLENS_DEMO.ACCOUNTS SET BALANCE = BALANCE + 50 WHERE ID = 1;
COMMIT;
SELECT * FROM LOCKLENS_DEMO.ACCOUNTS ORDER BY ID;
