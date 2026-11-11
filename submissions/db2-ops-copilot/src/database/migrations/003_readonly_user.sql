-- ============================================================================
-- 003_readonly_user.sql — least-privilege application account.
-- Run after 001_app_schema.sql (002 optional). NEVER executed during M1/M2
-- development. Idempotent: GRANTs may be repeated safely.
--
-- Replace :ro_user with the configured read-only user (DB2_RO_USER,
-- default db2ro). The password is generated locally (e.g. Python
-- `secrets.token_urlsafe(24)`) and stored ONLY in the gitignored .env
-- (DB2_RO_PASSWORD) — never in a file, log or commit.
--
-- Security model (defense in depth):
--   * The app connects as db2ro. The SQL validation gate rejects DDL/DML
--     before execution, but these GRANTs are the independent enforcement
--     layer if the gate is ever bypassed. DATABASE PERMISSIONS, NOT STATIC
--     VALIDATION, ARE THE BOUNDARY.
--   * SELECT on business tables; SELECT+INSERT on audit/history tables so
--     every request and query execution can be traced; SELECT+INSERT+DELETE
--     on the DB2VS vector table (the package's add_texts inserts, delete()
--     deletes, search selects).
--   * Explicitly NOT granted: UPDATE on audit/history (append-only), any
--     schema-level WRITE privilege, DBADM, BINDADD, or catalog write access.
--   * SYSCAT read access is what Db2 grants PUBLIC on catalog views; the
--     application additionally denies catalog schemas to GENERATED SQL via
--     the policy deny-list (application-owned introspection still works).
--
-- Usage: db2 -tvf database/migrations/003_readonly_user.sql  (after
-- substituting :ro_user — or edit the value before running).
-- ============================================================================

GRANT CONNECT ON DATABASE TO :ro_user;

-- Business / demo tables: read-only for the copilot query path.
GRANT SELECT ON APP.DEMO_SERVERS   TO :ro_user;
GRANT SELECT ON APP.DEMO_INCIDENTS TO :ro_user;

-- Audit trail and query-execution history: append + read (never UPDATE/DELETE).
GRANT SELECT, INSERT ON APP.APP_AUDIT        TO :ro_user;
GRANT SELECT, INSERT ON APP.QUERY_EXECUTIONS TO :ro_user;

-- Knowledge-base bookkeeping: the runtime reads metadata for citations.
-- Ingestion (M3) writes via the instance owner, not this account.
GRANT SELECT ON APP.DOCUMENT_METADATA TO :ro_user;

-- DB2VS vector table (created by 004 with the package's exact DDL):
-- add_texts() INSERTs, delete() DELETEs, similarity search SELECTs.
GRANT SELECT, INSERT, DELETE ON :vector_table TO :ro_user;

COMMIT;
