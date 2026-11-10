-- NEEDLE BM25 keyword index (owner: bm25 agent). Db2 12.1.5, database VECDB, 32K pages.
-- Statements end with ';'. scripts/load_postings_in_codespace.py runs the part before the POST_LOAD marker line,
-- truncates and loads NEEDLE.POSTING from data/postings.jsonl.gz (built by `python -m needle.bm25 build`),
-- then runs the part after the marker. Re-runnable (SQL0601N / SQL0624N / SQL0605W / SQL0598W ignored).
--
-- BM25 = rank_bm25.BM25Okapi (k1 = 1.2, b = 0.75, epsilon = 0.25), see src/needle/bm25.py:
--   idf(t) = LN(N - DF + 0.5) - LN(DF + 0.5); if negative -> EPSILON * AVG_IDF
--   score  = SUM idf(t) * TF * (K1 + 1) / (TF + K1 * (1 - B + B * BM25_DL / AVGDL))
-- BM25_DL is the BM25 document length (analyzed tokens after stop words and the 512-term cap); it is stored
-- on every posting so the keyword leg reads only NEEDLE.POSTING (which carries the RCAC columns).
-- ROW_BUCKET / EMBARGO_UNTIL are copies of NEEDLE.ADV_DOC (copied after every load, below); after embargo changes
-- run NEEDLE.SYNC_POSTING_ACL(?) (sql/03_triage_proc.sql), which also recomputes the public-only statistics.
-- TERM_DF / CORPUS_STATS hold PUBLIC-corpus statistics only and no analyst may SELECT them (sql/04_rcac.sql);
-- analysts reach them only through NEEDLE.BM25_SEARCH / NEEDLE.TRIAGE (EXECUTE).

CREATE TABLE NEEDLE.POSTING (
  TERM           VARCHAR(128) NOT NULL,
  ADV_ID         VARCHAR(64)  NOT NULL,
  TF             SMALLINT     NOT NULL,
  BM25_DL        INTEGER      NOT NULL,
  ROW_BUCKET     SMALLINT     NOT NULL CHECK (ROW_BUCKET BETWEEN 0 AND 99),
  EMBARGO_UNTIL  TIMESTAMP
);

CREATE TABLE NEEDLE.TERM_DF (
  TERM  VARCHAR(128) NOT NULL PRIMARY KEY,
  DF    INTEGER      NOT NULL
);

-- One row (ID = 1). N / AVGDL / AVG_IDF are computed in Db2 from NEEDLE.POSTING after the load.
CREATE TABLE NEEDLE.CORPUS_STATS (
  ID        SMALLINT  NOT NULL PRIMARY KEY CHECK (ID = 1),
  N         INTEGER   NOT NULL,
  AVGDL     DOUBLE    NOT NULL,
  AVG_IDF   DOUBLE    NOT NULL,
  K1        DOUBLE    NOT NULL,
  B         DOUBLE    NOT NULL,
  EPSILON   DOUBLE    NOT NULL,
  BUILT_AT  TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP
);

-- @POST_LOAD
-- Unique index = primary key, clustered by TERM; INCLUDE makes the keyword leg index-only
-- (TF, BM25_DL and the two RCAC columns are read from the index leaf pages).
CREATE UNIQUE INDEX NEEDLE.POSTING_PK_IX ON NEEDLE.POSTING (TERM, ADV_ID)
  INCLUDE (TF, BM25_DL, ROW_BUCKET, EMBARGO_UNTIL) CLUSTER;

ALTER TABLE NEEDLE.POSTING ADD CONSTRAINT POSTING_PK PRIMARY KEY (TERM, ADV_ID);

CREATE INDEX NEEDLE.POSTING_ADV_IX ON NEEDLE.POSTING (ADV_ID);

-- H2: the build file carries no embargo, so ROW_BUCKET / EMBARGO_UNTIL are always copied from ADV_DOC here.
-- A reload can therefore never drop an embargo. Run as DB2INST1 (its RCAC row sees every row).
-- Keep these statements identical to NEEDLE.SYNC_POSTING_ACL in sql/03_triage_proc.sql.
MERGE INTO NEEDLE.POSTING P
USING (SELECT ADV_ID, ROW_BUCKET, EMBARGO_UNTIL FROM NEEDLE.ADV_DOC) D
   ON P.ADV_ID = D.ADV_ID
WHEN MATCHED AND (P.ROW_BUCKET <> D.ROW_BUCKET OR P.EMBARGO_UNTIL IS DISTINCT FROM D.EMBARGO_UNTIL) THEN
  UPDATE SET ROW_BUCKET = D.ROW_BUCKET, EMBARGO_UNTIL = D.EMBARGO_UNTIL;

-- C1: BM25 statistics are computed over PUBLIC postings only (no active embargo). Global statistics over all rows
-- let any analyst subtract visible postings from TERM_DF and recover the vocabulary of embargoed advisories.
-- Approximation: an embargoed advisory (visible to SEES_EMBARGO users) is scored with public-corpus statistics; a
-- query term that occurs only in embargoed advisories gets DF = 0 in NEEDLE.BM25_SEARCH.
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

CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE NEEDLE.POSTING WITH DISTRIBUTION AND INDEXES ALL');

CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE NEEDLE.TERM_DF WITH DISTRIBUTION AND INDEXES ALL');

CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE NEEDLE.CORPUS_STATS');
