-- ============================================================================
-- 004_vector_store.sql — vector-store table in the EXACT shape the official
-- langchain-db2 DB2VS package creates itself.
--
-- Verified against the package source (libs/langchain-db2/langchain_db2/
-- db2vs.py, function _create_table — see docs/VECTOR_STORE.md for the full
-- verified API contract). DB2VS builds its DDL as:
--
--     CREATE TABLE <name> (
--       id        CHAR(16) PRIMARY KEY NOT NULL,
--       <text>    CLOB,
--       metadata  BLOB,
--       embedding VECTOR(<embedding_dim>, FLOAT32)
--     )
--
-- WHY PRE-CREATE (instead of letting DB2VS create it at runtime):
--   1. The application connects as the READ-ONLY account (db2ro), which has
--      no CREATE TABLE privilege. DB2VS's constructor calls an internal
--      _create_table(); when the table already exists it detects that
--      (SYSCAT count check) and skips creation — no CREATE needed.
--   2. The embedding dimension (768 for nomic-embed-text:v1.5) is fixed here
--      so the DDL is deterministic and reviewable.
--
-- TEXT COLUMN: the default DB2VS text_field is "text" (unquoted → stored
-- upper-case as TEXT). VECTOR requires Db2 12.1.2+ (verify with db2level).
--
-- NEVER executed during M1/M2 development (no Db2 on the dev machine).
-- Ordering: run AFTER 001 (APP schema must exist).
-- ============================================================================

--#SET TERMINATOR @
BEGIN
  DECLARE cnt INT DEFAULT 0;
  SELECT COUNT(*) INTO cnt FROM SYSCAT.TABLES
    WHERE TABSCHEMA = 'APP' AND TABNAME = 'COPILOT_KB';
  IF cnt = 0 THEN
    EXECUTE IMMEDIATE '
      CREATE TABLE APP.COPILOT_KB (
        id        CHAR(16) PRIMARY KEY NOT NULL,
        text      CLOB,
        metadata  BLOB,
        embedding VECTOR(768, FLOAT32)
      )';
  END IF;
END@
--#SET TERMINATOR ;

COMMIT;

-- Optional but recommended: a metadata-source index for operator queries.
-- (DB2VS performs similarity search with VECTOR_DISTANCE over the table;
-- ANN/HNSW vector indexes are documented as future work in the package.)
--#SET TERMINATOR @
BEGIN
  DECLARE cnt INT DEFAULT 0;
  SELECT COUNT(*) INTO cnt FROM SYSCAT.INDEXES
    WHERE INDSCHEMA = 'APP' AND INDNAME = 'IDX_VECTOR_ID';
  IF cnt = 0 THEN
    EXECUTE IMMEDIATE
      'CREATE INDEX APP.IDX_VECTOR_ID ON APP.COPILOT_KB (id)';
  END IF;
END@
--#SET TERMINATOR ;

COMMIT;
