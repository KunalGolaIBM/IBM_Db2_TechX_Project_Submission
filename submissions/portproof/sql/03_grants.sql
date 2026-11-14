-- Least privilege for the runtime user (DB2_USER).
-- It can read the ledger and CALL the procedures. It cannot INSERT, UPDATE or
-- DELETE any ledger table directly, and it cannot create objects.
-- Statements are separated by a line containing only --@

GRANT SELECT ON PORTPROOF.STATEMENT TO USER PPAPP
--@
GRANT SELECT ON PORTPROOF.STATEMENT_HIST TO USER PPAPP
--@
GRANT SELECT ON PORTPROOF.VERDICT TO USER PPAPP
--@
GRANT SELECT ON PORTPROOF.MQT_FAILURE_BY_CODE TO USER PPAPP
--@
GRANT EXECUTE ON PROCEDURE PORTPROOF.RECORD_TRANSLATION TO USER PPAPP
--@
GRANT EXECUTE ON PROCEDURE PORTPROOF.RECORD_VERDICT TO USER PPAPP
--@
GRANT EXECUTE ON PROCEDURE PORTPROOF.ESCALATE_STALLED TO USER PPAPP
--@
-- The vector fix-memory table is created by langchain-db2 (DB2VS) under the
-- owner. The runtime user reads it and appends accepted fixes.
GRANT SELECT, INSERT ON PORTPROOF.FIX_MEMORY TO USER PPAPP
