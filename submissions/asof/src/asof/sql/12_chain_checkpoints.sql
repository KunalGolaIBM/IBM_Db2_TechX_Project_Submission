-- Chain checkpoints: verify only what was appended since the last verified position.
-- VERIFY_CHAIN (03_procedures.sql) recomputes every row hash from the first row, which takes minutes at a million rows.
-- VERIFY_CHAIN_FROM_CHECKPOINT starts at the latest checkpoint instead. It re-checks the checkpoint row itself (still
-- there, still the hash that was verified, content still matching it), then every row after it as VERIFY_CHAIN does
-- (consecutive IDs, each link, each row's content, its citations, the chain head), and records the new position.
-- VERIFY_CHAIN stays as it is, for audits.
-- The boundary: rows before the checkpoint are not recomputed. An owner who drops the triggers and edits an old row
-- without touching its stored hashes is caught by the full VERIFY_CHAIN only; a rebuild that rewrote stored row
-- hashes is also caught by the external anchors (asof/anchor.py). A checkpoint is a row in Db2 that the owner could
-- write too: it saves time, it adds no trust. See docs/chain_benchmark.md.

-- table: CHAIN_CHECKPOINT
-- One row per successful verify: the head it reached (LEDGER_ID and that row's ROW_HASH), the first row it recomputed,
-- how many rows that was, when, and who (the Db2 user, and the API user who asked, if any). Written only by
-- VERIFY_CHAIN_FROM_CHECKPOINT; append-only like the ledger. It holds no policy text and no domain's decisions, only
-- positions and hashes, so it needs no row permission; only the runtime user may read it.
CREATE TABLE ASOF.CHAIN_CHECKPOINT (
  CHECKPOINT_ID  BIGINT       NOT NULL GENERATED ALWAYS AS IDENTITY (NO CACHE),
  LEDGER_ID      BIGINT       NOT NULL,
  ROW_HASH       CHAR(64)     NOT NULL,
  FROM_LEDGER_ID BIGINT       NOT NULL,
  ROWS_CHECKED   BIGINT       NOT NULL,
  KIND           VARCHAR(12)  NOT NULL,
  VERIFIED_AT    TIMESTAMP(6) NOT NULL DEFAULT CURRENT TIMESTAMP,
  VERIFIED_BY    VARCHAR(128) NOT NULL DEFAULT SESSION_USER,
  REQUESTED_BY   VARCHAR(40),
  CONSTRAINT PK_CHAIN_CHECKPOINT PRIMARY KEY (CHECKPOINT_ID),
  CONSTRAINT CK_CHECKPOINT_KIND CHECK (KIND IN ('FULL', 'INCREMENTAL')),
  CONSTRAINT CK_CHECKPOINT_RANGE CHECK (LEDGER_ID >= 1 AND FROM_LEDGER_ID BETWEEN 1 AND LEDGER_ID
                                        AND ROWS_CHECKED BETWEEN 1 AND LEDGER_ID - FROM_LEDGER_ID + 1),
  CONSTRAINT CK_CHECKPOINT_HASH CHECK (TRANSLATE(ROW_HASH, '', '0123456789abcdef') = '')
) IN ASOF_TS32K
@

-- trigger: CHAIN_CHECKPOINT_NO_UPDATE
CREATE OR REPLACE TRIGGER ASOF.CHAIN_CHECKPOINT_NO_UPDATE
  NO CASCADE BEFORE UPDATE ON ASOF.CHAIN_CHECKPOINT
  FOR EACH ROW
  SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'CHAIN_CHECKPOINT is append-only: rows cannot be updated'
@

-- trigger: CHAIN_CHECKPOINT_NO_DELETE
CREATE OR REPLACE TRIGGER ASOF.CHAIN_CHECKPOINT_NO_DELETE
  NO CASCADE BEFORE DELETE ON ASOF.CHAIN_CHECKPOINT
  FOR EACH ROW
  SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'CHAIN_CHECKPOINT is append-only: rows cannot be deleted'
@

-- procedure: VERIFY_CHAIN_FROM_CHECKPOINT
-- P_FULL = 0: from the latest checkpoint (from the first row if there is none yet). P_FULL = 1: from the first row
-- whatever the checkpoints say. Either way a run that starts at the first row is recorded as FULL. Same OUT values as
-- VERIFY_CHAIN, plus the first row recomputed and the checkpoint written (0 when the chain is BROKEN or empty: nothing
-- is recorded then). The caller needs role ASOF_TEXT_READER, or it would hash masked text (75030), and role
-- ASOF_ALL_DOMAINS, or the row permissions (06_domain_permissions.sql) would hide other domains' rows and every gap
-- would look like a deletion (75031). The caller commits.
CREATE OR REPLACE PROCEDURE ASOF.VERIFY_CHAIN_FROM_CHECKPOINT (
    IN  P_FULL          SMALLINT,
    IN  P_REQUESTED_BY  VARCHAR(40),    -- '' when no API user is named
    OUT P_STATUS        VARCHAR(12),
    OUT P_CHECKED       BIGINT,
    OUT P_FIRST_BAD     BIGINT,
    OUT P_DETAIL        VARCHAR(300),
    OUT P_FROM_ID       BIGINT,
    OUT P_CHECKPOINT_ID BIGINT)
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  DECLARE V_PREV CHAR(64);
  DECLARE V_START BIGINT DEFAULT 1;
  DECLARE V_EXPECT BIGINT DEFAULT 1;
  DECLARE V_HEAD_ID BIGINT;
  DECLARE V_HEAD_HASH CHAR(64);
  DECLARE V_CP_ID BIGINT;
  DECLARE V_CP_HASH CHAR(64);
  DECLARE V_ID BIGINT;
  DECLARE V_REQUEST CHAR(36);
  DECLARE V_CREATED TIMESTAMP(12);
  DECLARE V_CHANNEL VARCHAR(20);
  DECLARE V_DOC VARCHAR(32);
  DECLARE V_AS_OF DATE;
  DECLARE V_QUESTION VARCHAR(2000);
  DECLARE V_DRAFT VARCHAR(4000);
  DECLARE V_FINAL VARCHAR(4000);
  DECLARE V_DECISION VARCHAR(12);
  DECLARE V_REASON VARCHAR(40);
  DECLARE V_MODEL VARCHAR(200);
  DECLARE V_PROMPT VARCHAR(40);
  DECLARE V_LATENCY INTEGER;
  DECLARE V_VERDICTS VARCHAR(30000);
  DECLARE V_ROW_PREV CHAR(64);
  DECLARE V_ROW_HASH CHAR(64);
  DECLARE V_CITED INTEGER;
  DECLARE V_HASHED INTEGER;
  DECLARE V_UNMATCHED INTEGER;
  DECLARE V_DONE SMALLINT DEFAULT 0;
  DECLARE V_LAST BIGINT;
  DECLARE V_HEAD_NOW BIGINT;
  DECLARE V_CITE_FROM BIGINT DEFAULT 1;
  DECLARE C_ROWS CURSOR FOR
    SELECT LEDGER_ID, REQUEST_ID, CREATED_AT, CHANNEL, DOC_ID, AS_OF_DATE, QUESTION_REDACTED,
           DRAFT_REDACTED, FINAL_ANSWER, DECISION, REASON_CODE, MODEL_INFO, PROMPT_VERSION,
           LATENCY_MS, VERDICTS_JSON, PREV_HASH, ROW_HASH
    FROM ASOF.ANSWER_LEDGER WHERE LEDGER_ID >= V_START AND LEDGER_ID <= V_HEAD_ID ORDER BY LEDGER_ID;
  DECLARE C_CITES CURSOR FOR
    SELECT LEDGER_ID, VERDICTS_JSON FROM ASOF.ANSWER_LEDGER
    WHERE LEDGER_ID >= V_CITE_FROM AND LEDGER_ID <= V_HEAD_ID ORDER BY LEDGER_ID;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET V_DONE = 1;

  IF VERIFY_ROLE_FOR_USER(SESSION_USER, 'ASOF_TEXT_READER') <> 1 THEN
    SIGNAL SQLSTATE '75030' SET MESSAGE_TEXT = 'VERIFY_CHAIN_FROM_CHECKPOINT needs role ASOF_TEXT_READER: ledger text is masked for this user';
  END IF;
  IF VERIFY_ROLE_FOR_USER(SESSION_USER, 'ASOF_ALL_DOMAINS') <> 1 THEN
    SIGNAL SQLSTATE '75031' SET MESSAGE_TEXT = 'VERIFY_CHAIN_FROM_CHECKPOINT needs role ASOF_ALL_DOMAINS: row permissions hide other domains'' rows from this user';
  END IF;
  SET V_PREV = REPEAT('0', 64);
  SET (P_STATUS, P_CHECKED, P_FIRST_BAD, P_DETAIL, P_FROM_ID, P_CHECKPOINT_ID) = ('OK', 0, NULL, NULL, 1, 0);
  -- The head first, as in VERIFY_CHAIN: rows appended while this runs are checked on the next run.
  SET (V_HEAD_ID, V_HEAD_HASH) = (SELECT LAST_LEDGER_ID, LAST_HASH FROM ASOF.CHAIN_HEAD WHERE HEAD_ID = 1);
  SET V_HEAD_ID = COALESCE(V_HEAD_ID, -1);

  IF COALESCE(P_FULL, 0) = 0 THEN
    SET (V_CP_ID, V_CP_HASH) = (SELECT LEDGER_ID, ROW_HASH FROM ASOF.CHAIN_CHECKPOINT
                                ORDER BY CHECKPOINT_ID DESC FETCH FIRST 1 ROW ONLY);
  END IF;

  IF V_CP_ID IS NOT NULL THEN
    -- The checkpoint row itself: still there, still the hash that was verified, its content still matching it.
    SET P_FROM_ID = V_CP_ID;
    SET V_DONE = 0;
    SELECT LEDGER_ID, REQUEST_ID, CREATED_AT, CHANNEL, DOC_ID, AS_OF_DATE, QUESTION_REDACTED, DRAFT_REDACTED,
           FINAL_ANSWER, DECISION, REASON_CODE, MODEL_INFO, PROMPT_VERSION, LATENCY_MS, VERDICTS_JSON, PREV_HASH, ROW_HASH
      INTO V_ID, V_REQUEST, V_CREATED, V_CHANNEL, V_DOC, V_AS_OF, V_QUESTION, V_DRAFT, V_FINAL, V_DECISION, V_REASON,
           V_MODEL, V_PROMPT, V_LATENCY, V_VERDICTS, V_ROW_PREV, V_ROW_HASH
      FROM ASOF.ANSWER_LEDGER WHERE LEDGER_ID = V_CP_ID;
    IF V_DONE = 1 OR V_CP_ID > V_HEAD_ID THEN
      SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', V_CP_ID, 'the checkpoint row is missing or lies beyond the chain head');
    ELSEIF V_ROW_HASH <> V_CP_HASH THEN
      SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', V_CP_ID, 'the checkpoint row no longer has the hash it had when it was verified');
    ELSEIF ASOF.LEDGER_ROW_HASH(V_ROW_PREV, V_ID, V_REQUEST, V_CREATED, V_CHANNEL, V_DOC, V_AS_OF, V_QUESTION,
                                V_DRAFT, V_FINAL, V_DECISION, V_REASON, V_MODEL, V_PROMPT, V_LATENCY,
                                V_VERDICTS) <> V_ROW_HASH THEN
      SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', V_CP_ID, 'row content does not match its ROW_HASH');
    ELSE
      SET V_PREV = V_ROW_HASH;
      SET V_START = V_CP_ID + 1;
      SET V_EXPECT = V_CP_ID + 1;
      SET P_CHECKED = 1;
    END IF;
  END IF;

  IF P_STATUS = 'OK' THEN
    SET V_DONE = 0;
    OPEN C_ROWS;
    ROWS: LOOP
      FETCH C_ROWS INTO V_ID, V_REQUEST, V_CREATED, V_CHANNEL, V_DOC, V_AS_OF, V_QUESTION, V_DRAFT, V_FINAL,
                        V_DECISION, V_REASON, V_MODEL, V_PROMPT, V_LATENCY, V_VERDICTS, V_ROW_PREV, V_ROW_HASH;
      IF V_DONE = 1 THEN
        LEAVE ROWS;
      END IF;
      IF V_ID <> V_EXPECT THEN
        SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', V_EXPECT, 'ledger row is missing: IDs are not consecutive');
        LEAVE ROWS;
      END IF;
      IF V_ROW_PREV <> V_PREV THEN
        SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', V_ID, 'PREV_HASH does not match the previous row');
        LEAVE ROWS;
      END IF;
      IF ASOF.LEDGER_ROW_HASH(V_ROW_PREV, V_ID, V_REQUEST, V_CREATED, V_CHANNEL, V_DOC, V_AS_OF, V_QUESTION,
                              V_DRAFT, V_FINAL, V_DECISION, V_REASON, V_MODEL, V_PROMPT, V_LATENCY,
                              V_VERDICTS) <> V_ROW_HASH THEN
        SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', V_ID, 'row content does not match its ROW_HASH');
        LEAVE ROWS;
      END IF;
      SET V_PREV = V_ROW_HASH;
      SET V_EXPECT = V_EXPECT + 1;
      SET P_CHECKED = P_CHECKED + 1;
    END LOOP;
    CLOSE C_ROWS;
  END IF;

  IF P_STATUS = 'OK' AND (V_HEAD_ID < 0 OR V_HEAD_ID <> V_EXPECT - 1 OR V_HEAD_HASH <> V_PREV) THEN
    SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', V_EXPECT, 'chain head does not point at the last ledger row');
  END IF;
  IF P_STATUS = 'OK' THEN
    SET V_LAST = (SELECT MAX(LEDGER_ID) FROM ASOF.ANSWER_LEDGER);
    IF V_LAST > V_HEAD_ID THEN
      SET V_HEAD_NOW = (SELECT LAST_LEDGER_ID FROM ASOF.CHAIN_HEAD WHERE HEAD_ID = 1);
      IF V_LAST > COALESCE(V_HEAD_NOW, -1) THEN
        SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', COALESCE(V_HEAD_NOW, 0) + 1, 'a ledger row lies beyond the chain head');
      END IF;
    END IF;
  END IF;

  -- The citations of every row recomputed (the checkpoint row included) against its hashed verdicts, as VERIFY_CHAIN.
  IF P_STATUS = 'OK' AND P_CHECKED > 0 THEN
    SET V_DONE = 0;
    SET V_CITE_FROM = P_FROM_ID;
    OPEN C_CITES;
    CITES: LOOP
      FETCH C_CITES INTO V_ID, V_VERDICTS;
      IF V_DONE = 1 THEN
        LEAVE CITES;
      END IF;
      SET V_CITED = (SELECT COUNT(*) FROM ASOF.CLAIM_CITATION C WHERE C.LEDGER_ID = V_ID);
      SET V_HASHED = (SELECT COUNT(*) FROM TABLE(ASOF.CLAIMS_FROM_JSON(V_VERDICTS)) AS J);
      SET V_UNMATCHED = (
        SELECT COUNT(*) FROM ASOF.CLAIM_CITATION C
        WHERE C.LEDGER_ID = V_ID
          AND NOT EXISTS (
            SELECT 1 FROM TABLE(ASOF.CLAIMS_FROM_JSON(V_VERDICTS)) AS J
            WHERE J.PASS_NO = C.PASS_NO AND J.CLAIM_NO = C.CLAIM_NO AND J.VERDICT = C.VERDICT
              AND COALESCE(J.CLAUSE_ID, '') = COALESCE(C.CLAUSE_ID, '')
              AND COALESCE(J.CLAUSE_BUS_START, DATE('0001-01-01')) = COALESCE(C.CLAUSE_BUS_START, DATE('0001-01-01'))));
      IF V_CITED <> V_HASHED OR V_UNMATCHED > 0 THEN
        SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', V_ID, 'claim citations do not match the hashed verdicts');
        LEAVE CITES;
      END IF;
    END LOOP;
    CLOSE C_CITES;
  END IF;

  IF P_STATUS = 'OK' AND V_HEAD_ID >= 1 THEN
    INSERT INTO ASOF.CHAIN_CHECKPOINT (LEDGER_ID, ROW_HASH, FROM_LEDGER_ID, ROWS_CHECKED, KIND, REQUESTED_BY)
      VALUES (V_HEAD_ID, V_HEAD_HASH, P_FROM_ID, P_CHECKED,
              CASE WHEN P_FROM_ID = 1 AND V_CP_ID IS NULL THEN 'FULL' ELSE 'INCREMENTAL' END,
              NULLIF(TRIM(COALESCE(P_REQUESTED_BY, '')), ''));
    SET P_CHECKPOINT_ID = IDENTITY_VAL_LOCAL();
  END IF;
  -- The ibm_db CLI driver cannot return NULL OUT values (CLI0110E), so report 0 and a message.
  SET P_FIRST_BAD = COALESCE(P_FIRST_BAD, 0);
  SET P_DETAIL = COALESCE(P_DETAIL, CASE WHEN V_CP_ID IS NULL THEN 'every row, link and citation verified'
                                         ELSE 'the checkpoint row and every row, link and citation after it verified' END);
END
@
