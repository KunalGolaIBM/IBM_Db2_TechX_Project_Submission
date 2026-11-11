-- ============================================================================
-- 005_dba_tools.sql — setup for EXPLAIN and the DBA monitoring tools.
-- Run as the instance owner / a user with DBADM, AFTER 001-004.
--
-- STATUS: authored from IBM Db2 LUW documentation. NOT executed against a live
-- Db2 by this project (none was available). Review before running; every
-- statement is idempotent or safe to repeat.
--
-- Replace :ro_user with the configured read-only account (DB2_RO_USER).
-- ============================================================================

-- 1) EXPLAIN tables ----------------------------------------------------------
-- Creates EXPLAIN_INSTANCE, EXPLAIN_STATEMENT, EXPLAIN_OPERATOR, EXPLAIN_OBJECT,
-- ... in SYSTOOLS (NULL schema => SYSTOOLS), where Db2 looks when the session
-- user has no EXPLAIN tables of its own. Re-running reports the tables exist.
-- Matches DB2_EXPLAIN_SCHEMA=SYSTOOLS (the default).
CALL SYSPROC.SYSINSTALLOBJECTS(
  'EXPLAIN', 'C', CAST(NULL AS VARCHAR(128)), CAST(NULL AS VARCHAR(128)));

-- The app runs EXPLAIN PLAN, reads the plan back by QUERYTAG and deletes its
-- own rows, so it needs INSERT/SELECT/DELETE on these tables (nothing else).
GRANT SELECT, INSERT, DELETE ON SYSTOOLS.EXPLAIN_INSTANCE  TO :ro_user;
GRANT SELECT, INSERT, DELETE ON SYSTOOLS.EXPLAIN_STATEMENT TO :ro_user;
GRANT SELECT, INSERT, DELETE ON SYSTOOLS.EXPLAIN_ARGUMENT  TO :ro_user;
GRANT SELECT, INSERT, DELETE ON SYSTOOLS.EXPLAIN_OBJECT    TO :ro_user;
GRANT SELECT, INSERT, DELETE ON SYSTOOLS.EXPLAIN_OPERATOR  TO :ro_user;
GRANT SELECT, INSERT, DELETE ON SYSTOOLS.EXPLAIN_PREDICATE TO :ro_user;
GRANT SELECT, INSERT, DELETE ON SYSTOOLS.EXPLAIN_STREAM    TO :ro_user;

-- EXPLAIN also requires the privilege to EXPLAIN the underlying statement
-- (SELECT on the tables referenced) — the account already has this for the
-- tables it may query (migration 003).

-- 2) Monitoring tools (MON_GET_*) ---------------------------------------------
-- The monitor.* tools call MON_GET_TABLE, MON_GET_INDEX,
-- MON_GET_PKG_CACHE_STMT, MON_GET_CONNECTION, MON_GET_LOCKS and
-- MON_GET_BUFFERPOOL. Per the Db2 documentation each needs EXECUTE on the
-- function plus DATAACCESS, DBADM, SQLADM or WLMADM authority.
--
-- LEAST-PRIVILEGE RECOMMENDATION: do not widen the query account. Create a
-- separate monitoring account and point a second deployment (or the DBA
-- tools) at it. If you accept the trade-off for a demo, uncomment:
--
-- GRANT EXECUTE ON FUNCTION SYSPROC.MON_GET_TABLE          TO :ro_user;
-- GRANT EXECUTE ON FUNCTION SYSPROC.MON_GET_INDEX          TO :ro_user;
-- GRANT EXECUTE ON FUNCTION SYSPROC.MON_GET_PKG_CACHE_STMT TO :ro_user;
-- GRANT EXECUTE ON FUNCTION SYSPROC.MON_GET_CONNECTION     TO :ro_user;
-- GRANT EXECUTE ON FUNCTION SYSPROC.MON_GET_LOCKS          TO :ro_user;
-- GRANT EXECUTE ON FUNCTION SYSPROC.MON_GET_BUFFERPOOL     TO :ro_user;
-- GRANT SQLADM ON DATABASE TO USER :ro_user;
--
-- Without these grants the monitor.* tools return HTTP 403
-- DB_PERMISSION_DENIED (SQLSTATE 42501) with this hint; catalog.* tools work
-- with the default PUBLIC SELECT on SYSCAT.

-- 3) Verify (run manually) -------------------------------------------------------
-- SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = 'SYSTOOLS'
--   AND TABNAME LIKE 'EXPLAIN_%' ORDER BY TABNAME;

COMMIT;
