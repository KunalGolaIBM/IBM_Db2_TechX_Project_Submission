-- ============================================================================
-- 001_app_schema.sql — Db2 Ops Copilot application schema (IBM Db2 12.1.2+)
--
-- Target: IBM Db2 Community Edition (docker: icr.io/db2_community/db2).
-- NEVER executed during M1/M2 development (no Db2 on the dev machine).
-- Run manually as the instance owner AFTER the database exists — see
-- database/README.md. Migrations are idempotent: every object is created
-- only when absent (guarded via SYSCAT catalog checks in anonymous blocks).
--
-- All application objects live in the dedicated APP schema so the denied
-- system schemas (SYSCAT, SYSIBM, ...) stay untouched and the read-only
-- account can be granted exactly what it needs.
--
-- Ordering: 001 (schema) -> 002 (indexes) -> 003 (grants) -> 004 (vector).
-- Rollback: see database/README.md "Rollback and recovery".
-- ============================================================================

-- Dedicated application schema (owned by the instance owner, not db2ro).
--#SET TERMINATOR @
BEGIN
  DECLARE cnt INT DEFAULT 0;
  SELECT COUNT(*) INTO cnt FROM SYSCAT.SCHEMATA WHERE SCHEMANAME = 'APP';
  IF cnt = 0 THEN
    EXECUTE IMMEDIATE 'CREATE SCHEMA APP';
  END IF;
END@
--#SET TERMINATOR ;

COMMIT;

-- ----------------------------------------------------------------------------
-- DEMO_SERVERS / DEMO_INCIDENTS — synthetic demo fleet for the text-to-SQL
-- path. Harmless sample data; no real systems are described.
-- ----------------------------------------------------------------------------
--#SET TERMINATOR @
BEGIN
  DECLARE cnt INT DEFAULT 0;
  SELECT COUNT(*) INTO cnt FROM SYSCAT.TABLES
    WHERE TABSCHEMA = 'APP' AND TABNAME = 'DEMO_SERVERS';
  IF cnt = 0 THEN
    EXECUTE IMMEDIATE '
      CREATE TABLE APP.DEMO_SERVERS (
        SERVER_ID   INTEGER       NOT NULL PRIMARY KEY,
        HOSTNAME    VARCHAR(64)   NOT NULL,
        ENVIRONMENT VARCHAR(16)   NOT NULL,
        OWNER_TEAM  VARCHAR(32),
        UPTIME_PCT  DECIMAL(5, 2)
      )';
  END IF;
END@
--#SET TERMINATOR ;

--#SET TERMINATOR @
BEGIN
  DECLARE cnt INT DEFAULT 0;
  SELECT COUNT(*) INTO cnt FROM SYSCAT.TABLES
    WHERE TABSCHEMA = 'APP' AND TABNAME = 'DEMO_INCIDENTS';
  IF cnt = 0 THEN
    EXECUTE IMMEDIATE '
      CREATE TABLE APP.DEMO_INCIDENTS (
        INCIDENT_ID INTEGER     NOT NULL PRIMARY KEY,
        SERVER_ID   INTEGER     REFERENCES APP.DEMO_SERVERS (SERVER_ID),
        SEVERITY    INTEGER     NOT NULL,
        OPENED_AT   TIMESTAMP   NOT NULL,
        RESOLVED_AT TIMESTAMP
      )';
  END IF;
END@
--#SET TERMINATOR ;

-- Seed data idempotently (replace-in-place, demo content only).
DELETE FROM APP.DEMO_SERVERS;
INSERT INTO APP.DEMO_SERVERS (SERVER_ID, HOSTNAME, ENVIRONMENT, OWNER_TEAM, UPTIME_PCT) VALUES
    (1, 'db2-prod-01',   'prod',    'platform',  99.95),
    (2, 'db2-prod-02',   'prod',    'platform',  99.87),
    (3, 'db2-stage-01',  'staging', 'data-eng',  98.40),
    (4, 'db2-dev-01',    'dev',     'data-eng',  92.10);

DELETE FROM APP.DEMO_INCIDENTS;
INSERT INTO APP.DEMO_INCIDENTS (INCIDENT_ID, SERVER_ID, SEVERITY, OPENED_AT, RESOLVED_AT) VALUES
    (101, 1, 2, '2026-10-28 09:15:00', '2026-10-28 11:02:00'),
    (102, 3, 3, '2026-10-29 14:40:00', NULL),
    (103, 4, 1, '2026-10-30 08:05:00', '2026-10-30 08:31:00'),
    (104, 2, 4, '2026-10-30 10:22:00', NULL);

COMMIT;

-- ----------------------------------------------------------------------------
-- APP_AUDIT — every copilot request is recorded for enterprise traceability:
-- who (actor/session), what (intent/question/generated SQL), which operation,
-- outcome (status) and how long (latency), plus a SANITIZED metadata CLOB.
--
-- Security: METADATA must never contain passwords, tokens or full
-- connection strings — the application strips them before insert
-- (app/adapters/audit/db2_audit.py sanitization step). The read-only
-- account receives SELECT + INSERT only (003_readonly_user.sql).
-- ----------------------------------------------------------------------------
--#SET TERMINATOR @
BEGIN
  DECLARE cnt INT DEFAULT 0;
  SELECT COUNT(*) INTO cnt FROM SYSCAT.TABLES
    WHERE TABSCHEMA = 'APP' AND TABNAME = 'APP_AUDIT';
  IF cnt = 0 THEN
    EXECUTE IMMEDIATE '
      CREATE TABLE APP.APP_AUDIT (
        AUDIT_ID      BIGINT      NOT NULL GENERATED ALWAYS AS IDENTITY
                        (START WITH 1, INCREMENT BY 1, CACHE 20) PRIMARY KEY,
        REQ_TS        TIMESTAMP   NOT NULL DEFAULT CURRENT TIMESTAMP,
        ACTOR_TYPE    VARCHAR(32) NOT NULL DEFAULT ''copilot_user'',
        SESSION_ID    VARCHAR(64),
        CLIENT_REQ_ID VARCHAR(64),
        OPERATION     VARCHAR(32) NOT NULL DEFAULT ''chat'',
        INTENT        VARCHAR(16) NOT NULL,
        QUESTION      CLOB,
        SQL_TEXT      CLOB,
        STATUS        VARCHAR(24) NOT NULL,
        LATENCY_MS    INTEGER,
        METADATA      CLOB
      )';
  END IF;
END@
--#SET TERMINATOR ;

COMMIT;

-- ----------------------------------------------------------------------------
-- DOCUMENT_METADATA — one row per knowledge-base document chunk indexed into
-- the vector store. The vector EMBEDDING itself lives in the DB2VS-managed
-- table (see 004_vector_store.sql); this table owns the operational
-- metadata used for citation display, re-ingestion bookkeeping and
-- metadata filters. METADATA is a sanitized JSON CLOB.
-- ----------------------------------------------------------------------------
--#SET TERMINATOR @
BEGIN
  DECLARE cnt INT DEFAULT 0;
  SELECT COUNT(*) INTO cnt FROM SYSCAT.TABLES
    WHERE TABSCHEMA = 'APP' AND TABNAME = 'DOCUMENT_METADATA';
  IF cnt = 0 THEN
    EXECUTE IMMEDIATE '
      CREATE TABLE APP.DOCUMENT_METADATA (
        DOC_ID       VARCHAR(64)  NOT NULL PRIMARY KEY,
        SOURCE       VARCHAR(255) NOT NULL,
        TITLE        VARCHAR(255),
        URI          VARCHAR(1024),
        CHUNK_INDEX  INTEGER      NOT NULL DEFAULT 0,
        CHUNK_COUNT  INTEGER      NOT NULL DEFAULT 1,
        CHAR_COUNT   INTEGER,
        CONTENT_HASH VARCHAR(64),
        METADATA     CLOB,
        CREATED_AT   TIMESTAMP    NOT NULL DEFAULT CURRENT TIMESTAMP,
        UPDATED_AT   TIMESTAMP    NOT NULL DEFAULT CURRENT TIMESTAMP
      )';
  END IF;
END@
--#SET TERMINATOR ;

COMMIT;

-- ----------------------------------------------------------------------------
-- QUERY_EXECUTIONS — one row per executed (or rejected-at-execution) query:
-- the SQL text, validation outcome, EXPLAIN dry-run outcome, execution
-- status, row count, truncation flag, latency and SQLSTATE when failed.
-- The read-only account receives SELECT + INSERT (003_readonly_user.sql).
-- ----------------------------------------------------------------------------
--#SET TERMINATOR @
BEGIN
  DECLARE cnt INT DEFAULT 0;
  SELECT COUNT(*) INTO cnt FROM SYSCAT.TABLES
    WHERE TABSCHEMA = 'APP' AND TABNAME = 'QUERY_EXECUTIONS';
  IF cnt = 0 THEN
    EXECUTE IMMEDIATE '
      CREATE TABLE APP.QUERY_EXECUTIONS (
        EXECUTION_ID      BIGINT      NOT NULL GENERATED ALWAYS AS IDENTITY
                            (START WITH 1, INCREMENT BY 1, CACHE 20) PRIMARY KEY,
        REQ_TS            TIMESTAMP   NOT NULL DEFAULT CURRENT TIMESTAMP,
        CLIENT_REQ_ID     VARCHAR(64),
        SQL_TEXT          CLOB        NOT NULL,
        VALIDATION_STATUS VARCHAR(16) NOT NULL,
        EXPLAIN_STATUS    VARCHAR(24),
        EXECUTION_STATUS  VARCHAR(24) NOT NULL,
        ROW_COUNT         INTEGER,
        TRUNCATED         CHAR(1)     NOT NULL DEFAULT ''N'',
        LATENCY_MS        INTEGER,
        SQLSTATE_CODE     CHAR(5),
        METADATA          CLOB
      )';
  END IF;
END@
--#SET TERMINATOR ;

COMMIT;
