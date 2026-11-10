--#SET TERMINATOR @
-- NEEDLE hybrid triage (owner: bm25 agent). Db2 12.1.5, VECDB. Statement terminator: '@'
--   run: db2 -td@ -vf sql/03_triage_proc.sql      (prerequisites: sql/01_schema.sql, sql/02_bm25.sql loaded)
--
-- NEEDLE.BM25_SEARCH(P_QTERMS, P_DEPTH)  keyword leg, plain SQL BM25 over NEEDLE.POSTING (inline table function;
--                                         the ONE copy of the BM25 SQL, also used by tests/test_bm25_parity.py)
-- NEEDLE.TRIAGE_MODE(P_QVEC, P_QTERMS, P_K, P_DEPTH, P_MODE)  P_MODE = 'HYBRID' | 'KW' | 'VEC'
-- NEEDLE.TRIAGE(P_QVEC, P_QTERMS, P_K, P_DEPTH)              = TRIAGE_MODE(..., 'HYBRID')  (contract signature)
--   result set: ADV_ID, RRF, KW_RANK, VEC_RANK, VEC_DIST ordered by RRF DESC, ADV_ID ASC
--
-- Query terms: P_QTERMS is ONE JSON array of strings, e.g. ["pyyaml","cve-2021-44228"], expanded inside Db2.
-- The ISO JSON_TABLE in Db2 12.1.5 accepts only the row path 'strict $' (one row per document), so the array is
-- walked with a recursive common table expression over JSON_VALUE(doc, 'strict $.t[i]') (same pattern as
-- sql/99_validation.sql V3; a root-level '$[i]' path returned NULL, so the array is wrapped as {"t": [...]}).
-- A legacy SYSTOOLS.JSON_TABLE(SYSTOOLS.JSON2BSON(...)) expansion was measured and rejected: its BM25 top-10
-- differed from rank_bm25 on 29 of 30 queries (docs/evidence/triage_explain.md).
-- Terms are never concatenated into SQL text; only validated INTEGERs (k, depth) are.
--
-- One statement per call, no temporary table: every row is read from NEEDLE.ADV_DOC / NEEDLE.POSTING under the
-- caller's RCAC row permission (SESSION_USER). Vector leg = a CTE with
--   ORDER BY VECTOR_DISTANCE(...) FETCH APPROX FIRST <depth literal> ROWS ONLY
-- (FETCH APPROX FIRST ? never uses the vector index on 12.1.5; EXPLAIN shows IXSCAN on ADV_DOC_VIX inside the CTE).
-- Fusion: RRF(d) = 1/(60 + KW_RANK) + 1/(60 + VEC_RANK); ranks by RANK() OVER with ADV_ID as tie-break;
-- FULL OUTER JOIN. Choose P_DEPTH > P_K: a permission-filtered APPROX leg can return fewer than P_DEPTH rows.

CREATE OR REPLACE FUNCTION NEEDLE.BM25_SEARCH (P_QTERMS CLOB(32K), P_DEPTH INTEGER)
  RETURNS TABLE (ADV_ID VARCHAR(64), KW_SCORE DOUBLE, KW_RANK BIGINT)
  LANGUAGE SQL
  SPECIFIC NEEDLE_BM25_SEARCH
  READS SQL DATA
  NO EXTERNAL ACTION
  RETURN
    WITH QJ (DOC) AS (
           SELECT '{"t":' || COALESCE(P_QTERMS, CAST('[]' AS CLOB(32K))) || '}' FROM SYSIBM.SYSDUMMY1),
         -- recursive walk of $.t[0], $.t[1], ...; NULL past the end of the array stops the recursion
         QA (I, TERM) AS (
           SELECT 0, JSON_VALUE(QJ.DOC, 'strict $.t[0]' RETURNING VARCHAR(512) NULL ON EMPTY NULL ON ERROR)
           FROM QJ
           UNION ALL
           SELECT QA.I + 1,
                  JSON_VALUE(QJ.DOC, 'strict $.t[' || VARCHAR(QA.I + 1) || ']'
                             RETURNING VARCHAR(512) NULL ON EMPTY NULL ON ERROR)
           FROM QA, QJ WHERE QA.TERM IS NOT NULL AND QA.I < 2047),
         QT (TERM) AS (
           SELECT DISTINCT CAST(TERM AS VARCHAR(128)) FROM QA
           WHERE TERM IS NOT NULL AND LENGTH(TERM) <= 128),
         CS (N, AVGDL, AVG_IDF, K1, B, EPSILON) AS (
           SELECT DOUBLE(N), AVGDL, AVG_IDF, K1, B, EPSILON FROM NEEDLE.CORPUS_STATS WHERE ID = 1),
         -- TERM_DF / CORPUS_STATS are PUBLIC-corpus statistics (no embargoed rows; sql/02_bm25.sql).
         -- A term missing from TERM_DF is kept (DF = 0) only if the CALLER can see a posting for it: the EXISTS reads
         -- NEEDLE.POSTING under the caller's RCAC, so it only matters for users who may see embargoed rows.
         -- query pruning: at most 64 such terms, lowest DF first (mirrors needle.bm25.prune_query_terms)
         QD (TERM, DF) AS (
           SELECT QT.TERM, COALESCE(T.DF, 0) FROM QT LEFT JOIN NEEDLE.TERM_DF T ON T.TERM = QT.TERM
           WHERE T.DF IS NOT NULL
              OR EXISTS (SELECT 1 FROM NEEDLE.POSTING P0 WHERE P0.TERM = QT.TERM)
           ORDER BY COALESCE(T.DF, 0), QT.TERM FETCH FIRST 64 ROWS ONLY),
         -- rank_bm25.BM25Okapi IDF: ln(N - df + 0.5) - ln(df + 0.5); negative -> EPSILON * AVG_IDF
         QI (TERM, IDF) AS (
           SELECT QD.TERM,
                  CASE WHEN LN(CS.N - QD.DF + 0.5E0) - LN(QD.DF + 0.5E0) < 0
                       THEN CS.EPSILON * CS.AVG_IDF
                       ELSE LN(CS.N - QD.DF + 0.5E0) - LN(QD.DF + 0.5E0) END
           FROM QD, CS),
         -- LATERAL binds the term before POSTING is read, so each query term is one index probe on POSTING_PK_IX.
         -- With a plain join, the RCAC row permission on POSTING made Db2 scan the whole index (1.94M entries)
         -- and hash-join it with the terms (docs/evidence/rcac_posting_overhead.md).
         KS (ADV_ID, KW_SCORE) AS (
           SELECT P.ADV_ID,
                  SUM(QI.IDF * (P.TF * (CS.K1 + 1E0)
                      / (P.TF + CS.K1 * (1E0 - CS.B + CS.B * P.BM25_DL / CS.AVGDL))))
           FROM QI, CS,
                LATERAL (SELECT P1.ADV_ID, P1.TF, P1.BM25_DL FROM NEEDLE.POSTING P1 WHERE P1.TERM = QI.TERM) AS P
           GROUP BY P.ADV_ID),
         -- rank on the score rounded to 9 decimals: the summation order of the per-term parts depends on the plan,
         -- so equal scores can differ in the last bit; rounding makes the ADV_ID tie-break plan-independent.
         KR (ADV_ID, KW_SCORE, KW_RANK) AS (
           SELECT ADV_ID, KW_SCORE, RANK() OVER (ORDER BY ROUND(KW_SCORE, 9) DESC, ADV_ID) FROM KS WHERE KW_SCORE > 0)
    SELECT ADV_ID, KW_SCORE, KW_RANK FROM KR WHERE KW_RANK <= P_DEPTH
@

CREATE OR REPLACE PROCEDURE NEEDLE.TRIAGE_MODE (
    IN P_QVEC   CLOB(100K),
    IN P_QTERMS CLOB(32K),
    IN P_K      INTEGER,
    IN P_DEPTH  INTEGER,
    IN P_MODE   VARCHAR(6))
  LANGUAGE SQL
  SPECIFIC NEEDLE_TRIAGE_MODE
  DYNAMIC RESULT SETS 1
  READS SQL DATA
BEGIN
  DECLARE V_MODE  VARCHAR(6);
  DECLARE V_K     VARCHAR(11);
  DECLARE V_DEPTH VARCHAR(11);
  DECLARE V_VEC0  VARCHAR(1000);
  DECLARE V_KW    VARCHAR(1000);
  DECLARE V_FSQL  VARCHAR(4000);
  DECLARE S_OUT STATEMENT;
  DECLARE C_OUT CURSOR WITH RETURN TO CLIENT FOR S_OUT;

  SET V_MODE = UPPER(COALESCE(P_MODE, 'HYBRID'));
  IF V_MODE NOT IN ('HYBRID', 'KW', 'VEC') THEN
    SIGNAL SQLSTATE '22023' SET MESSAGE_TEXT = 'P_MODE must be HYBRID, KW or VEC';
  END IF;
  IF P_K IS NULL OR P_K < 1 OR P_K > 1000 THEN
    SIGNAL SQLSTATE '22023' SET MESSAGE_TEXT = 'P_K must be 1..1000';
  END IF;
  IF P_DEPTH IS NULL OR P_DEPTH < 1 OR P_DEPTH > 1000 THEN
    SIGNAL SQLSTATE '22023' SET MESSAGE_TEXT = 'P_DEPTH must be 1..1000';
  END IF;
  IF V_MODE IN ('HYBRID', 'VEC') AND P_QVEC IS NULL THEN
    SIGNAL SQLSTATE '22023' SET MESSAGE_TEXT = 'P_QVEC is required for HYBRID and VEC';
  END IF;
  -- the only values concatenated into SQL text: two validated INTEGERs
  SET V_K = RTRIM(CHAR(P_K));
  SET V_DEPTH = RTRIM(CHAR(P_DEPTH));

  IF V_MODE = 'KW' THEN
    SET V_VEC0 = 'SELECT CAST(NULL AS VARCHAR(64)), CAST(NULL AS DOUBLE) FROM SYSIBM.SYSDUMMY1 WHERE 1 = 0';
  ELSE
    SET V_VEC0 = 'SELECT ADV_ID, DOUBLE(VECTOR_DISTANCE(EMB, VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32), COSINE)) '
              || 'FROM NEEDLE.ADV_DOC '
              || 'ORDER BY VECTOR_DISTANCE(EMB, VECTOR(CAST(? AS CLOB(100K)), 768, FLOAT32), COSINE) '
              || 'FETCH APPROX FIRST ' || V_DEPTH || ' ROWS ONLY';
  END IF;
  IF V_MODE = 'VEC' THEN
    SET V_KW = 'SELECT CAST(NULL AS VARCHAR(64)), CAST(NULL AS BIGINT) FROM SYSIBM.SYSDUMMY1 WHERE 1 = 0';
  ELSE
    SET V_KW = 'SELECT B.ADV_ID, B.KW_RANK FROM TABLE(NEEDLE.BM25_SEARCH(CAST(? AS CLOB(32K)), '
            || V_DEPTH || ')) AS B';
  END IF;

  SET V_FSQL =
       'WITH VEC0 (ADV_ID, VEC_DIST) AS (' || V_VEC0 || '), '
    || 'KW (ADV_ID, KW_RANK) AS (' || V_KW || '), '
    || 'VEC (ADV_ID, VEC_DIST, VEC_RANK) AS ('
    || '  SELECT ADV_ID, VEC_DIST, RANK() OVER (ORDER BY VEC_DIST, ADV_ID) FROM VEC0), '
    || 'F (ADV_ID, RRF, KW_RANK, VEC_RANK, VEC_DIST) AS ('
    || '  SELECT COALESCE(K.ADV_ID, V.ADV_ID), '
    || '         COALESCE(1E0 / (60 + K.KW_RANK), 0E0) + COALESCE(1E0 / (60 + V.VEC_RANK), 0E0), '
    || '         K.KW_RANK, V.VEC_RANK, V.VEC_DIST '
    || '  FROM KW K FULL OUTER JOIN VEC V ON K.ADV_ID = V.ADV_ID) '
    || 'SELECT ADV_ID, RRF, INTEGER(KW_RANK) AS KW_RANK, INTEGER(VEC_RANK) AS VEC_RANK, VEC_DIST '
    || 'FROM F ORDER BY RRF DESC, ADV_ID FETCH FIRST ' || V_K || ' ROWS ONLY';
  PREPARE S_OUT FROM V_FSQL;
  IF V_MODE = 'HYBRID' THEN
    OPEN C_OUT USING P_QVEC, P_QVEC, P_QTERMS;
  ELSEIF V_MODE = 'VEC' THEN
    OPEN C_OUT USING P_QVEC, P_QVEC;
  ELSE
    OPEN C_OUT USING P_QTERMS;
  END IF;
END
@

CREATE OR REPLACE PROCEDURE NEEDLE.TRIAGE (
    IN P_QVEC   CLOB(100K),
    IN P_QTERMS CLOB(32K),
    IN P_K      INTEGER,
    IN P_DEPTH  INTEGER)
  LANGUAGE SQL
  SPECIFIC NEEDLE_TRIAGE
  DYNAMIC RESULT SETS 1
  READS SQL DATA
BEGIN
  CALL NEEDLE.TRIAGE_MODE(P_QVEC, P_QTERMS, P_K, P_DEPTH, 'HYBRID');
END
@

-- Re-copy ROW_BUCKET / EMBARGO_UNTIL from ADV_DOC into POSTING, then recompute the PUBLIC-only BM25 statistics
-- (TERM_DF, CORPUS_STATS). Run after every embargo or bucket change, as DB2INST1 (its RCAC row sees all rows; the
-- statements read with the SESSION_USER's permission). Same statements as the POST_LOAD part of sql/02_bm25.sql.
-- Returns the number of updated posting rows.
CREATE OR REPLACE PROCEDURE NEEDLE.SYNC_POSTING_ACL (OUT P_UPDATED INTEGER)
  LANGUAGE SQL
  SPECIFIC NEEDLE_SYNC_POSTING_ACL
  MODIFIES SQL DATA
BEGIN
  MERGE INTO NEEDLE.POSTING P
  USING (SELECT ADV_ID, ROW_BUCKET, EMBARGO_UNTIL FROM NEEDLE.ADV_DOC) D
     ON P.ADV_ID = D.ADV_ID
  WHEN MATCHED AND (P.ROW_BUCKET <> D.ROW_BUCKET
                    OR P.EMBARGO_UNTIL IS DISTINCT FROM D.EMBARGO_UNTIL) THEN
    UPDATE SET ROW_BUCKET = D.ROW_BUCKET, EMBARGO_UNTIL = D.EMBARGO_UNTIL;
  GET DIAGNOSTICS P_UPDATED = ROW_COUNT;

  DELETE FROM NEEDLE.TERM_DF;
  INSERT INTO NEEDLE.TERM_DF (TERM, DF)
    SELECT TERM, COUNT(*) FROM NEEDLE.POSTING
    WHERE EMBARGO_UNTIL IS NULL OR EMBARGO_UNTIL <= CURRENT TIMESTAMP
    GROUP BY TERM;

  DELETE FROM NEEDLE.CORPUS_STATS;
  INSERT INTO NEEDLE.CORPUS_STATS (ID, N, AVGDL, AVG_IDF, K1, B, EPSILON)
    WITH D (ADV_ID, DL) AS (SELECT ADV_ID, MAX(BM25_DL) FROM NEEDLE.POSTING
                            WHERE EMBARGO_UNTIL IS NULL OR EMBARGO_UNTIL <= CURRENT TIMESTAMP
                            GROUP BY ADV_ID),
         S (N, AVGDL) AS (SELECT COUNT(*), AVG(DOUBLE(DL)) FROM D)
    SELECT 1, S.N, S.AVGDL,
           (SELECT AVG(LN(DOUBLE(S.N) - T.DF + 0.5) - LN(DOUBLE(T.DF) + 0.5)) FROM NEEDLE.TERM_DF T),
           1.2, 0.75, 0.25
    FROM S;
END
@
