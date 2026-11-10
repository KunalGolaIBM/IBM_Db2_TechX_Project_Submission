-- PortProof schema. Run as the schema owner (DB2_SETUP_USER), not the runtime user.
-- Statements are separated by a line containing only --@
-- Db2 Community Edition 12.1.5.0

DROP TABLE PORTPROOF.VERDICT
--@
DROP TABLE PORTPROOF.STATEMENT
--@
DROP TABLE PORTPROOF.STATEMENT_HIST
--@
-- The migration unit. System-versioned: every change to a statement's state is
-- kept by the engine, so the whole migration is replayable with FOR SYSTEM_TIME AS OF.
CREATE TABLE PORTPROOF.STATEMENT (
  STMT_ID       INTEGER       NOT NULL GENERATED ALWAYS AS IDENTITY,
  CASE_NAME     VARCHAR(80)   NOT NULL,
  SRC_DIALECT   VARCHAR(16)   NOT NULL,
  SRC_SQL       VARCHAR(4000) NOT NULL,
  DB2_SQL       VARCHAR(4000),
  STATUS        VARCHAR(24)   NOT NULL,
  ATTEMPTS      SMALLINT      NOT NULL DEFAULT 0,
  LAST_SQLCODE  INTEGER,
  LAST_ERROR    VARCHAR(1200),
  META          VARCHAR(2000),
  SYS_START     TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW BEGIN,
  SYS_END       TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW END,
  TRANS_ID      TIMESTAMP(12) GENERATED ALWAYS AS TRANSACTION START ID,
  PERIOD SYSTEM_TIME (SYS_START, SYS_END),
  CONSTRAINT PK_STATEMENT PRIMARY KEY (STMT_ID),
  CONSTRAINT UQ_STATEMENT_CASE UNIQUE (CASE_NAME),
  CONSTRAINT CK_ST_DIALECT CHECK (SRC_DIALECT IN ('postgres', 'mysql')),
  CONSTRAINT CK_ST_ATTEMPTS CHECK (ATTEMPTS BETWEEN 0 AND 10),
  CONSTRAINT CK_ST_STATUS CHECK (STATUS IN (
    'TRANSLATE_FAIL', 'COMPILE_FAIL', 'COMPILES', 'REPAIRED',
    'PROVEN_EQUIVALENT', 'PROVEN_DIFFERENT', 'UNSTABLE', 'VACUOUS',
    'ESCALATED'))
)
--@
CREATE TABLE PORTPROOF.STATEMENT_HIST LIKE PORTPROOF.STATEMENT
--@
ALTER TABLE PORTPROOF.STATEMENT ADD VERSIONING USE HISTORY TABLE PORTPROOF.STATEMENT_HIST
--@
-- Proof records. One row per verdict Db2 itself produced.
CREATE TABLE PORTPROOF.VERDICT (
  VERDICT_ID  INTEGER       NOT NULL GENERATED ALWAYS AS IDENTITY,
  STMT_ID     INTEGER       NOT NULL,
  KIND        VARCHAR(16)   NOT NULL,
  OUTCOME     VARCHAR(24)   NOT NULL,
  INSTANCES   SMALLINT      NOT NULL DEFAULT 0,
  DETAIL      VARCHAR(8000),
  CERT_SHA    VARCHAR(64),
  CREATED_AT  TIMESTAMP     NOT NULL DEFAULT CURRENT TIMESTAMP,
  CONSTRAINT PK_VERDICT PRIMARY KEY (VERDICT_ID),
  CONSTRAINT FK_VERDICT_STMT FOREIGN KEY (STMT_ID)
    REFERENCES PORTPROOF.STATEMENT (STMT_ID) ON DELETE CASCADE,
  CONSTRAINT CK_VD_KIND CHECK (KIND IN ('COMPILE', 'SEMANTIC', 'PHYSICAL')),
  -- VACUOUS and UNSTABLE are verdicts in their own right, and both exist to
  -- stop a stronger one being claimed. VACUOUS: the engines agreed, and the
  -- agreement is worthless because neither returned any rows. UNSTABLE: the
  -- engines differ, and the source engine differs from *itself* when the same
  -- rows are inserted in another order, so the statement's ORDER BY never
  -- determined an answer and Db2 is not at fault. Folding either into
  -- EQUIVALENT or DIFFERENT is the mistake this column makes impossible.
  CONSTRAINT CK_VD_OUTCOME CHECK (OUTCOME IN (
    'PASS', 'FAIL', 'EQUIVALENT', 'DIFFERENT', 'UNSTABLE', 'VACUOUS',
    'INCONCLUSIVE', 'ADVICE')),
  CONSTRAINT CK_VD_INSTANCES CHECK (INSTANCES >= 0)
)
--@
CREATE INDEX PORTPROOF.IX_VERDICT_STMT ON PORTPROOF.VERDICT (STMT_ID, KIND)
--@
-- Expression-based index, so case-insensitive case-name lookups are indexed.
-- Note (measured on CE 12.1.5): COLLATION_KEY_BIT works in a *predicate* but is
-- rejected as an index key expression (SQL0356N reason 23), so the indexable
-- form is UPPER(). PortProof emits the collation-key form for comparison
-- semantics and this form when an index is needed.
CREATE INDEX PORTPROOF.IX_STMT_CASEFOLD
  ON PORTPROOF.STATEMENT (UPPER(CASE_NAME))
--@
-- Dialect-failure rollup, maintained by the engine on every insert.
DROP TABLE PORTPROOF.MQT_FAILURE_BY_CODE
--@
CREATE TABLE PORTPROOF.MQT_FAILURE_BY_CODE AS (
  SELECT SRC_DIALECT, LAST_SQLCODE, COUNT(*) AS N
  FROM PORTPROOF.STATEMENT
  -- Negative SQLCODEs only. "IS NOT NULL" also matches 0, which is a
  -- *successful* compile, so the failure rollup would have counted successes
  -- as failures.
  WHERE LAST_SQLCODE < 0
  GROUP BY SRC_DIALECT, LAST_SQLCODE
) DATA INITIALLY DEFERRED REFRESH IMMEDIATE
  MAINTAINED BY SYSTEM
--@
SET INTEGRITY FOR PORTPROOF.MQT_FAILURE_BY_CODE IMMEDIATE CHECKED NOT INCREMENTAL
