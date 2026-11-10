-- 04_rcac.sql  NEEDLE row and column access control (RCAC).  Owner: rcac agent.
--
-- Run as DB2INST1 inside the container (DB2INST1 holds SECADM, DBADM, ACCESSCTRL, DATAACCESS: SYSCAT.DBAUTH):
--   docker exec -i db2 su - db2inst1 -c "db2 connect to VECDB && db2 -tvf /tmp/04_rcac.sql"
-- Prerequisites:
--   * 01_schema.sql: NEEDLE.ADV_DOC loaded, vector index NEEDLE.ADV_DOC_VIX built, RUNSTATS done
--   * 02_bm25.sql + 03_triage_proc.sql: NEEDLE.POSTING / TERM_DF / CORPUS_STATS, NEEDLE.TRIAGE, NEEDLE.SYNC_POSTING_ACL
--   * Linux users created inside the db2 container (Db2 uses OS authentication): scripts/rcac_users.sh
--     Passwords exist only in needle/.env as NDL_<ROLE>_PASSWORD.
--
-- Policy (contract): a user sees a row when ROW_BUCKET < USER_ACCESS.MAX_BUCKET for SESSION_USER
-- AND (the row is not under embargo OR USER_ACCESS.SEES_EMBARGO = 1).  ROW_BUCKET is 0..99 (hash of CANON_ID),
-- so MAX_BUCKET is the visible percentage.  A user without a USER_ACCESS row sees nothing (scalar subquery is NULL).
-- DB2INST1 is listed with full access because the loaders, the eval harness and the BM25 build connect as DB2INST1:
-- once row access control is active, every user, DB2INST1 included, is filtered.
--
-- Experiment note (docs/evidence/rcac_synthetic.md, docs/evidence/rcac_real.md): the optimizer gives the permission
-- predicate one fixed filter factor for every user, and the DiskANN index scan returns about k / filter-factor
-- candidates that the permission then filters.  Low-visibility users get fewer than k rows from FETCH APPROX.
-- src/needle/rcac.py (router) compensates outside the engine.

------------------------------------------------------------------------------------------------------------------
-- Step 1. Entitlement table (immutable during experiments).  No user other than DB2INST1 gets any privilege on it.
------------------------------------------------------------------------------------------------------------------
CREATE TABLE NEEDLE.USER_ACCESS (
  AUTHID        VARCHAR(128) NOT NULL PRIMARY KEY,
  MAX_BUCKET    SMALLINT     NOT NULL CHECK (MAX_BUCKET BETWEEN 0 AND 100),
  SEES_EMBARGO  SMALLINT     NOT NULL DEFAULT 0 CHECK (SEES_EMBARGO IN (0, 1))
);

DELETE FROM NEEDLE.USER_ACCESS;
INSERT INTO NEEDLE.USER_ACCESS (AUTHID, MAX_BUCKET, SEES_EMBARGO) VALUES
  ('DB2INST1',   100, 1),   -- loader / admin / eval harness
  ('NDL_SENIOR', 100, 1),   -- demo: sees everything including embargoed advisories
  ('NDL_JUNIOR', 100, 0),   -- demo: sees everything except embargoed advisories
  ('NDL_P10',     10, 0),   -- selectivity sweep users
  ('NDL_P25',     25, 0),
  ('NDL_P50',     50, 0),
  ('NDL_P75',     75, 0);

CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE NEEDLE.USER_ACCESS WITH DISTRIBUTION AND INDEXES ALL');

-- Everything below needs loaded data (embargo marking, POSTING sync) and must run AFTER the bulk load:
-- scripts/setup_db.sh runs the section after this marker once loading is done.  Both safeguards apply:
-- activation happens post-load, and the loader identity DB2INST1 has an explicit full-access USER_ACCESS row
-- (MAX_BUCKET 100, SEES_EMBARGO 1), so later reloads by DB2INST1 still see and may insert every row.
-- @POST_LOAD

------------------------------------------------------------------------------------------------------------------
-- Step 2. Demo embargo (separate, documented data step).  OSV has no embargo field, so we mark a realistic small set:
-- the 25 most recently published, non-withdrawn GHSA advisories, embargoed for 60 days from the time this runs.
-- The embargo is applied by CANON_ID so that an alias record (for example the PYSEC copy of the same vulnerability)
-- cannot reveal an embargoed advisory.  POSTING carries copies of ROW_BUCKET / EMBARGO_UNTIL; re-sync them.
------------------------------------------------------------------------------------------------------------------
UPDATE NEEDLE.ADV_DOC
   SET EMBARGO_UNTIL = CURRENT TIMESTAMP + 60 DAYS
 WHERE CANON_ID IN (SELECT CANON_ID FROM NEEDLE.ADV_DOC
                     WHERE KIND = 'GHSA' AND WITHDRAWN IS NULL
                     ORDER BY PUBLISHED DESC, ADV_ID
                     FETCH FIRST 25 ROWS ONLY);

-- Step 2b. SYNTHETIC DEMO EMBARGO FLAG ON A REAL ADVISORY (for the demo only; OSV publishes this advisory openly).
-- GHSA-5x8w-8jj5-q52h (Pillow: heap buffer overflow in FlashPix (FPX) JPEG decoding, published 2026-10-23) affects
-- services in the demo fleet, so NDL_SENIOR sees affected services that NDL_JUNIOR cannot see at all.
-- Applied after the RCAC measurements were frozen (docs/evidence/rcac_real.md); every row sharing its CANON_ID.
UPDATE NEEDLE.ADV_DOC
   SET EMBARGO_UNTIL = CURRENT TIMESTAMP + 60 DAYS
 WHERE CANON_ID IN (SELECT CANON_ID FROM NEEDLE.ADV_DOC WHERE ADV_ID = 'GHSA-5x8w-8jj5-q52h');

CALL NEEDLE.SYNC_POSTING_ACL(?);

------------------------------------------------------------------------------------------------------------------
-- Step 3. Row permissions and column mask.
------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE PERMISSION NEEDLE.ADV_DOC_ROWS ON NEEDLE.ADV_DOC
  FOR ROWS WHERE
        ROW_BUCKET < (SELECT UA.MAX_BUCKET FROM NEEDLE.USER_ACCESS UA WHERE UA.AUTHID = SESSION_USER)
    AND (   EMBARGO_UNTIL IS NULL
         OR EMBARGO_UNTIL <= CURRENT TIMESTAMP
         OR (SELECT UA.SEES_EMBARGO FROM NEEDLE.USER_ACCESS UA WHERE UA.AUTHID = SESSION_USER) = 1)
  ENFORCED FOR ALL ACCESS
  ENABLE;

CREATE OR REPLACE PERMISSION NEEDLE.POSTING_ROWS ON NEEDLE.POSTING
  FOR ROWS WHERE
        ROW_BUCKET < (SELECT UA.MAX_BUCKET FROM NEEDLE.USER_ACCESS UA WHERE UA.AUTHID = SESSION_USER)
    AND (   EMBARGO_UNTIL IS NULL
         OR EMBARGO_UNTIL <= CURRENT TIMESTAMP
         OR (SELECT UA.SEES_EMBARGO FROM NEEDLE.USER_ACCESS UA WHERE UA.AUTHID = SESSION_USER) = 1)
  ENFORCED FOR ALL ACCESS
  ENABLE;

-- ADV_ALIAS and ADV_AFFECTED have no ROW_BUCKET column but carry ADV_ID, and the app reads them as the end user
-- (retriever.py: aliases, sbom.py: affected versions).  Without a permission they would list embargoed IDs.
-- The predicate is repeated in full (it does not rely on ADV_DOC's own permission inside this subquery).
CREATE OR REPLACE PERMISSION NEEDLE.ADV_ALIAS_ROWS ON NEEDLE.ADV_ALIAS
  FOR ROWS WHERE EXISTS (
    SELECT 1 FROM NEEDLE.ADV_DOC D, NEEDLE.USER_ACCESS UA
     WHERE D.ADV_ID = NEEDLE.ADV_ALIAS.ADV_ID
       AND UA.AUTHID = SESSION_USER
       AND D.ROW_BUCKET < UA.MAX_BUCKET
       AND (D.EMBARGO_UNTIL IS NULL OR D.EMBARGO_UNTIL <= CURRENT TIMESTAMP OR UA.SEES_EMBARGO = 1))
  ENFORCED FOR ALL ACCESS
  ENABLE;

CREATE OR REPLACE PERMISSION NEEDLE.ADV_AFFECTED_ROWS ON NEEDLE.ADV_AFFECTED
  FOR ROWS WHERE EXISTS (
    SELECT 1 FROM NEEDLE.ADV_DOC D, NEEDLE.USER_ACCESS UA
     WHERE D.ADV_ID = NEEDLE.ADV_AFFECTED.ADV_ID
       AND UA.AUTHID = SESSION_USER
       AND D.ROW_BUCKET < UA.MAX_BUCKET
       AND (D.EMBARGO_UNTIL IS NULL OR D.EMBARGO_UNTIL <= CURRENT TIMESTAMP OR UA.SEES_EMBARGO = 1))
  ENFORCED FOR ALL ACCESS
  ENABLE;

-- Defense in depth: even if a row permission is later relaxed (for example to show that an embargoed advisory
-- exists), the text of an embargoed advisory stays hidden from users without SEES_EMBARGO.
-- Observed on Db2 12.1.5.0: a mask on the CLOB column DETAILS is rejected with
--   SQL0350N  The column "DETAILS" was implicitly or explicitly referenced in a context where the data type of
--   the column is not supported.  SQLSTATE=42962
-- so DETAILS is protected by the row permission alone, and the mask covers SUMMARY (VARCHAR), the text the app
-- shows and the LLM summarizes.
CREATE OR REPLACE MASK NEEDLE.ADV_DOC_SUMMARY_MASK ON NEEDLE.ADV_DOC
  FOR COLUMN SUMMARY RETURN
    CASE WHEN EMBARGO_UNTIL IS NULL OR EMBARGO_UNTIL <= CURRENT TIMESTAMP THEN SUMMARY
         WHEN (SELECT UA.SEES_EMBARGO FROM NEEDLE.USER_ACCESS UA WHERE UA.AUTHID = SESSION_USER) = 1 THEN SUMMARY
         ELSE CAST('[embargoed]' AS VARCHAR(2000))
    END
  ENABLE;

------------------------------------------------------------------------------------------------------------------
-- Step 4. Least-privilege grants (CONNECT, SELECT, EXECUTE only).  No grant on USER_ACCESS or ADV_RAW.
------------------------------------------------------------------------------------------------------------------
GRANT CONNECT ON DATABASE TO USER NDL_SENIOR, USER NDL_JUNIOR, USER NDL_P10, USER NDL_P25, USER NDL_P50, USER NDL_P75;

-- Demo users: everything the app (TRIAGE, retriever, SBOM join) reads as the end user.
GRANT SELECT ON NEEDLE.ADV_DOC      TO USER NDL_SENIOR, USER NDL_JUNIOR;
GRANT SELECT ON NEEDLE.POSTING      TO USER NDL_SENIOR, USER NDL_JUNIOR;
-- C1 fix (bm25 agent): no analyst may SELECT NEEDLE.TERM_DF / NEEDLE.CORPUS_STATS. NEEDLE.BM25_SEARCH reads them
-- with its definer's authority; analysts reach them only through EXECUTE on BM25_SEARCH / TRIAGE / TRIAGE_MODE.
-- The REVOKEs undo the grants of earlier runs (SQL0556N "not revoked ... does not hold" is expected on a new database).
REVOKE SELECT ON NEEDLE.TERM_DF      FROM USER NDL_SENIOR, USER NDL_JUNIOR;
REVOKE SELECT ON NEEDLE.CORPUS_STATS FROM USER NDL_SENIOR, USER NDL_JUNIOR;
GRANT SELECT ON NEEDLE.ADV_ALIAS    TO USER NDL_SENIOR, USER NDL_JUNIOR;
GRANT SELECT ON NEEDLE.ADV_AFFECTED TO USER NDL_SENIOR, USER NDL_JUNIOR;
GRANT EXECUTE ON PROCEDURE NEEDLE.TRIAGE      TO USER NDL_SENIOR, USER NDL_JUNIOR;
GRANT EXECUTE ON PROCEDURE NEEDLE.TRIAGE_MODE TO USER NDL_SENIOR, USER NDL_JUNIOR;
GRANT EXECUTE ON FUNCTION  NEEDLE.BM25_SEARCH TO USER NDL_SENIOR, USER NDL_JUNIOR;

-- Sweep users: the vector table, plus what NEEDLE.TRIAGE reads, so the selectivity sweep can also run TRIAGE.
GRANT SELECT ON NEEDLE.ADV_DOC      TO USER NDL_P10, USER NDL_P25, USER NDL_P50, USER NDL_P75;
GRANT SELECT ON NEEDLE.POSTING      TO USER NDL_P10, USER NDL_P25, USER NDL_P50, USER NDL_P75;
REVOKE SELECT ON NEEDLE.TERM_DF      FROM USER NDL_P10, USER NDL_P25, USER NDL_P50, USER NDL_P75;
REVOKE SELECT ON NEEDLE.CORPUS_STATS FROM USER NDL_P10, USER NDL_P25, USER NDL_P50, USER NDL_P75;
GRANT EXECUTE ON PROCEDURE NEEDLE.TRIAGE      TO USER NDL_P10, USER NDL_P25, USER NDL_P50, USER NDL_P75;
GRANT EXECUTE ON PROCEDURE NEEDLE.TRIAGE_MODE TO USER NDL_P10, USER NDL_P25, USER NDL_P50, USER NDL_P75;
GRANT EXECUTE ON FUNCTION  NEEDLE.BM25_SEARCH TO USER NDL_P10, USER NDL_P25, USER NDL_P50, USER NDL_P75;

-- BM25 statistics: global DF over all rows let an analyst reconstruct embargoed vocabulary (global DF minus the DF of
-- visible postings). Fixed by the bm25 agent: statistics are computed over public rows only (NEEDLE.SYNC_POSTING_ACL)
-- and analysts have no SELECT on NEEDLE.TERM_DF / NEEDLE.CORPUS_STATS (REVOKEs above).

-- After 05_sbom_temporal.sql has created the SBOM tables (they hold no advisory IDs, so no permission is needed):
--   GRANT SELECT ON NEEDLE.SERVICE        TO USER NDL_SENIOR, USER NDL_JUNIOR;
--   GRANT SELECT ON NEEDLE.SBOM_COMPONENT TO USER NDL_SENIOR, USER NDL_JUNIOR;

------------------------------------------------------------------------------------------------------------------
-- Step 5. Activate.  From here on every query on these tables, by every user, is filtered by the permissions.
------------------------------------------------------------------------------------------------------------------
ALTER TABLE NEEDLE.ADV_DOC      ACTIVATE ROW ACCESS CONTROL ACTIVATE COLUMN ACCESS CONTROL;
ALTER TABLE NEEDLE.POSTING      ACTIVATE ROW ACCESS CONTROL;
ALTER TABLE NEEDLE.ADV_ALIAS    ACTIVATE ROW ACCESS CONTROL;
ALTER TABLE NEEDLE.ADV_AFFECTED ACTIVATE ROW ACCESS CONTROL;

-- Verify (CONTROL: R = row, C = column, B = both).
SELECT TABNAME, CONTROL FROM SYSCAT.TABLES WHERE TABSCHEMA = 'NEEDLE' AND CONTROL <> ' ' ORDER BY TABNAME;
SELECT CONTROLNAME, TABNAME, CONTROLTYPE, ENABLE, VALID FROM SYSCAT.CONTROLS WHERE TABSCHEMA = 'NEEDLE' ORDER BY CONTROLNAME;
SELECT COUNT(*) AS EMBARGOED_ROWS FROM NEEDLE.ADV_DOC WHERE EMBARGO_UNTIL > CURRENT TIMESTAMP;

-- Rollback (SECADM):
--   ALTER TABLE NEEDLE.ADV_DOC DEACTIVATE ROW ACCESS CONTROL DEACTIVATE COLUMN ACCESS CONTROL;
--   ALTER TABLE NEEDLE.POSTING DEACTIVATE ROW ACCESS CONTROL;  (same for ADV_ALIAS, ADV_AFFECTED)
