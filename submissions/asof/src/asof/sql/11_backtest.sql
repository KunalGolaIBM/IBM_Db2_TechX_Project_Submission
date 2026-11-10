-- Backtests (asof/backtest.py): a CSV of past answers, each checked through the normal check and recorded in the ledger
-- as a decision on channel 'backtest', then summarised as an exposure report. The ledger row is the evidence; these
-- tables say which run and which CSV row it came from, the outcome Db2 derived from that row, and the money difference
-- Db2 read out of the cited clause version's RULE_JSON. Written only through the procedures below (the runtime user
-- holds EXECUTE on them and SELECT, nothing else). Items and costs are append-only; a run changes only while it runs.
-- No text from the CSV is stored here: the redacted question and draft are in the ledger row, under its column masks.
-- SQLSTATEs 75071 to 75079 are this file's refusals.

-- other: CK_LEDGER_CHANNEL_BACKTEST
-- Ledgers created before backtests existed refuse channel 'backtest'. This replaces the check with the list in
-- 01_tables.sql (the two lists must stay equal; tests/test_backtest.py compares them). Db2 re-validates the existing
-- rows, one scan of ANSWER_LEDGER per setup run.
ALTER TABLE ASOF.ANSWER_LEDGER DROP CONSTRAINT CK_LEDGER_CHANNEL
  ADD CONSTRAINT CK_LEDGER_CHANNEL CHECK (CHANNEL IN ('chat', 'email', 'faq', 'api', 'eval', 'demo', 'agent', 'backtest'))
@

-- table: BACKTEST_RUN
-- One uploaded file. DOC_ID is the policy document for rows that name none ('auto': Db2's routing vote decides per
-- row, and a close call is held, not guessed). DEADLINE_AT: no row starts after it. A run that has made no progress
-- for STALE_AFTER_S seconds (its process died) reads as INTERRUPTED in V_BACKTEST_RUNS.
CREATE TABLE ASOF.BACKTEST_RUN (
  RUN_ID           BIGINT        NOT NULL GENERATED ALWAYS AS IDENTITY (NO CACHE),
  SOURCE_NAME      VARCHAR(200)  NOT NULL,
  SOURCE_SHA256    CHAR(64)      NOT NULL,
  ROW_COUNT        SMALLINT      NOT NULL,
  DOC_ID           VARCHAR(32)   NOT NULL,
  MODEL_INFO       VARCHAR(200)  NOT NULL,
  IS_SAMPLE        SMALLINT      NOT NULL DEFAULT 0,
  STATUS           VARCHAR(12)   NOT NULL DEFAULT 'RUNNING',
  NOTE             VARCHAR(400),
  DEADLINE_AT      TIMESTAMP     NOT NULL,
  STALE_AFTER_S    INTEGER       NOT NULL,
  LAST_PROGRESS_AT TIMESTAMP     NOT NULL DEFAULT CURRENT TIMESTAMP,
  REQUESTED_BY     VARCHAR(40),
  CREATED_AT       TIMESTAMP     NOT NULL DEFAULT CURRENT TIMESTAMP,
  CREATED_BY       VARCHAR(128)  NOT NULL DEFAULT SESSION_USER,
  FINISHED_AT      TIMESTAMP,
  CONSTRAINT PK_BACKTEST_RUN PRIMARY KEY (RUN_ID),
  CONSTRAINT CK_BACKTEST_RUN_STATUS CHECK (STATUS IN ('RUNNING', 'DONE', 'DEADLINE', 'STOPPED', 'FAILED')),
  CONSTRAINT CK_BACKTEST_RUN_ROWS CHECK (ROW_COUNT BETWEEN 1 AND 500),
  CONSTRAINT CK_BACKTEST_RUN_HASH CHECK (TRANSLATE(SOURCE_SHA256, '', '0123456789abcdef') = ''),
  CONSTRAINT CK_BACKTEST_RUN_SAMPLE CHECK (IS_SAMPLE IN (0, 1)),
  CONSTRAINT CK_BACKTEST_RUN_STALE CHECK (STALE_AFTER_S BETWEEN 60 AND 86400),
  CONSTRAINT CK_BACKTEST_RUN_FINISHED CHECK ((STATUS = 'RUNNING') = (FINISHED_AT IS NULL))
) IN ASOF_TS32K
@

-- table: BACKTEST_ITEM
-- One CSV row. OUTCOME is derived by ADD_BACKTEST_ITEM from the row's ledger decision, never taken from the caller:
--   WRONG        a claim contradicted the clause version in force on the customer's date (first pass)
--   UNCONFIRMED  nothing contradicted, but the policy in force does not confirm the answer: a claim no clause covers,
--                a detail no claim stated, too many claims, or no clear policy document (the decision was held)
--   OK           every claim supported, or the answer made no policy claim
--   FAILED       the check failed closed on an error, or its decision could not be recorded
--   SKIPPED      not checked: the run's deadline passed, or it was stopped (the spend hook)
CREATE TABLE ASOF.BACKTEST_ITEM (
  RUN_ID         BIGINT       NOT NULL,
  ROW_NO         SMALLINT     NOT NULL,
  CUSTOMER_DATE  DATE         NOT NULL,
  SOURCE_CHANNEL VARCHAR(20)  NOT NULL,
  DOC_ID         VARCHAR(32),
  LEDGER_ID      BIGINT,
  OUTCOME        VARCHAR(12)  NOT NULL,
  REASON_CODE    VARCHAR(40)  NOT NULL,
  DETAIL         VARCHAR(300),
  CREATED_AT     TIMESTAMP    NOT NULL DEFAULT CURRENT TIMESTAMP,
  CONSTRAINT PK_BACKTEST_ITEM PRIMARY KEY (RUN_ID, ROW_NO),
  CONSTRAINT FK_BACKTEST_ITEM_RUN FOREIGN KEY (RUN_ID) REFERENCES ASOF.BACKTEST_RUN (RUN_ID),
  CONSTRAINT FK_BACKTEST_ITEM_LEDGER FOREIGN KEY (LEDGER_ID) REFERENCES ASOF.ANSWER_LEDGER (LEDGER_ID),
  CONSTRAINT FK_BACKTEST_ITEM_DOC FOREIGN KEY (DOC_ID) REFERENCES ASOF.POLICY_DOC (DOC_ID),
  CONSTRAINT CK_BACKTEST_ITEM_OUTCOME CHECK (OUTCOME IN ('WRONG', 'UNCONFIRMED', 'OK', 'FAILED', 'SKIPPED')),
  CONSTRAINT CK_BACKTEST_ITEM_CHANNEL CHECK (SOURCE_CHANNEL IN ('chat', 'email', 'faq', 'api')),
  CONSTRAINT CK_BACKTEST_ITEM_CHECKED CHECK (OUTCOME IN ('FAILED', 'SKIPPED') OR LEDGER_ID IS NOT NULL),
  CONSTRAINT CK_BACKTEST_ITEM_SKIPPED CHECK (OUTCOME <> 'SKIPPED' OR LEDGER_ID IS NULL)
) IN ASOF_TS32K
@

-- index: UX_BACKTEST_ITEM_LEDGER
-- A ledger decision belongs to at most one CSV row.
CREATE UNIQUE INDEX ASOF.UX_BACKTEST_ITEM_LEDGER ON ASOF.BACKTEST_ITEM (LEDGER_ID) EXCLUDE NULL KEYS
@

-- table: BACKTEST_COST
-- One row per contradicted claim of a WRONG item: the money difference, or why there is none. COMPUTED: the claim
-- states one dollar amount, the cited clause version sets one, under RULE_KEY; POLICY_USD is what JSON_VALUE reads
-- from that version's RULE_JSON inside ADD_BACKTEST_COST. FAVOURS: CUSTOMER when the answer promised a lower fee or a
-- larger payment than the policy (what the company could be held to, as in Moffatt), COMPANY when it told the
-- customer to pay more or expect less. A key naming a fee is a charge; any other amount is a payment to the customer.
CREATE TABLE ASOF.BACKTEST_COST (
  RUN_ID           BIGINT        NOT NULL,
  ROW_NO           SMALLINT      NOT NULL,
  CLAIM_NO         SMALLINT      NOT NULL,
  CLAUSE_ID        VARCHAR(32)   NOT NULL,
  CLAUSE_VERSION   VARCHAR(20)   NOT NULL,
  CLAUSE_BUS_START DATE          NOT NULL,
  STATUS           VARCHAR(16)   NOT NULL,
  RULE_KEY         VARCHAR(64),
  STATED_USD       DECIMAL(11, 2),
  POLICY_USD       DECIMAL(11, 2),
  DIFF_USD         DECIMAL(12, 2),
  FAVOURS          VARCHAR(10),
  NOTE             VARCHAR(200)  NOT NULL,
  CONSTRAINT PK_BACKTEST_COST PRIMARY KEY (RUN_ID, ROW_NO, CLAIM_NO),
  CONSTRAINT FK_BACKTEST_COST_ITEM FOREIGN KEY (RUN_ID, ROW_NO) REFERENCES ASOF.BACKTEST_ITEM (RUN_ID, ROW_NO),
  CONSTRAINT CK_BACKTEST_COST_STATUS CHECK (STATUS IN ('COMPUTED', 'NOT_COMPUTABLE')),
  CONSTRAINT CK_BACKTEST_COST_AMOUNTS CHECK ((STATUS = 'COMPUTED') = (RULE_KEY IS NOT NULL AND STATED_USD IS NOT NULL
                                             AND POLICY_USD IS NOT NULL AND DIFF_USD IS NOT NULL)),
  CONSTRAINT CK_BACKTEST_COST_DIFF CHECK (DIFF_USD IS NULL OR DIFF_USD = STATED_USD - POLICY_USD),
  CONSTRAINT CK_BACKTEST_COST_FAVOURS CHECK (FAVOURS IS NULL OR FAVOURS IN ('CUSTOMER', 'COMPANY')),
  CONSTRAINT CK_BACKTEST_COST_SIGN CHECK (STATED_USD IS NULL OR (STATED_USD >= 0 AND POLICY_USD >= 0))
) IN ASOF_TS32K
@

-- trigger: BACKTEST_RUN_NO_DELETE
CREATE OR REPLACE TRIGGER ASOF.BACKTEST_RUN_NO_DELETE
  NO CASCADE BEFORE DELETE ON ASOF.BACKTEST_RUN
  FOR EACH ROW
  SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'BACKTEST_RUN rows cannot be deleted'
@

-- trigger: BACKTEST_RUN_FINISHED_ONCE
-- A run changes only while it runs (its progress time, then its final status, once); what it was run on never changes.
CREATE OR REPLACE TRIGGER ASOF.BACKTEST_RUN_FINISHED_ONCE
  NO CASCADE BEFORE UPDATE ON ASOF.BACKTEST_RUN
  REFERENCING OLD AS O NEW AS N
  FOR EACH ROW
  WHEN (O.STATUS <> 'RUNNING' OR N.SOURCE_SHA256 <> O.SOURCE_SHA256 OR N.ROW_COUNT <> O.ROW_COUNT
        OR N.DOC_ID <> O.DOC_ID OR N.MODEL_INFO <> O.MODEL_INFO OR N.DEADLINE_AT <> O.DEADLINE_AT
        OR N.IS_SAMPLE <> O.IS_SAMPLE OR N.CREATED_AT <> O.CREATED_AT)
  SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'A backtest run changes only while it runs, and only its progress and outcome'
@

-- trigger: BACKTEST_ITEM_NO_UPDATE
CREATE OR REPLACE TRIGGER ASOF.BACKTEST_ITEM_NO_UPDATE
  NO CASCADE BEFORE UPDATE ON ASOF.BACKTEST_ITEM
  FOR EACH ROW
  SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'BACKTEST_ITEM is append-only: rows cannot be updated'
@

-- trigger: BACKTEST_ITEM_NO_DELETE
CREATE OR REPLACE TRIGGER ASOF.BACKTEST_ITEM_NO_DELETE
  NO CASCADE BEFORE DELETE ON ASOF.BACKTEST_ITEM
  FOR EACH ROW
  SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'BACKTEST_ITEM is append-only: rows cannot be deleted'
@

-- trigger: BACKTEST_COST_NO_UPDATE
CREATE OR REPLACE TRIGGER ASOF.BACKTEST_COST_NO_UPDATE
  NO CASCADE BEFORE UPDATE ON ASOF.BACKTEST_COST
  FOR EACH ROW
  SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'BACKTEST_COST is append-only: rows cannot be updated'
@

-- trigger: BACKTEST_COST_NO_DELETE
CREATE OR REPLACE TRIGGER ASOF.BACKTEST_COST_NO_DELETE
  NO CASCADE BEFORE DELETE ON ASOF.BACKTEST_COST
  FOR EACH ROW
  SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'BACKTEST_COST is append-only: rows cannot be deleted'
@

-- procedure: START_BACKTEST
-- Opens a run. 75071: a policy document Db2 does not hold (or 'auto'); 75079: a deadline or staleness limit out of
-- range. The row cap is CK_BACKTEST_RUN_ROWS (500), whatever the application's own setting.
CREATE OR REPLACE PROCEDURE ASOF.START_BACKTEST (
    IN  P_NAME        VARCHAR(200),
    IN  P_SHA256      CHAR(64),
    IN  P_ROWS        SMALLINT,
    IN  P_DOC_ID      VARCHAR(32),
    IN  P_MODEL       VARCHAR(200),
    IN  P_SAMPLE      SMALLINT,
    IN  P_DEADLINE_S  INTEGER,
    IN  P_STALE_S     INTEGER,
    IN  P_USER        VARCHAR(40),   -- '' when no API user is named
    OUT P_RUN_ID      BIGINT)
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  IF P_DOC_ID IS NULL OR (P_DOC_ID <> 'auto' AND NOT EXISTS (SELECT 1 FROM ASOF.POLICY_DOC WHERE DOC_ID = P_DOC_ID)) THEN
    SIGNAL SQLSTATE '75071' SET MESSAGE_TEXT = 'A backtest checks against a policy document Db2 holds, or auto';
  END IF;
  IF P_DEADLINE_S IS NULL OR P_DEADLINE_S NOT BETWEEN 1 AND 86400 OR P_STALE_S IS NULL THEN
    SIGNAL SQLSTATE '75079' SET MESSAGE_TEXT = 'A backtest deadline is 1 second to 1 day';
  END IF;
  INSERT INTO ASOF.BACKTEST_RUN (SOURCE_NAME, SOURCE_SHA256, ROW_COUNT, DOC_ID, MODEL_INFO, IS_SAMPLE, DEADLINE_AT,
                                 STALE_AFTER_S, REQUESTED_BY)
    VALUES (P_NAME, LOWER(P_SHA256), P_ROWS, P_DOC_ID, P_MODEL, P_SAMPLE, CURRENT TIMESTAMP + P_DEADLINE_S SECONDS,
            P_STALE_S, NULLIF(TRIM(COALESCE(P_USER, '')), ''));
  SET P_RUN_ID = IDENTITY_VAL_LOCAL();
END
@

-- procedure: ADD_BACKTEST_ITEM
-- Records one CSV row's outcome. With a ledger row (P_LEDGER_ID <> 0), Db2 checks that it is this run's check of this
-- row (channel 'backtest', the customer's date, the document, and the run and row hashed into its verdicts as
-- $.backtest), copies its reason code and derives the outcome from its decision and first-pass citations. Without one,
-- P_REASON says why: LEDGER_UNAVAILABLE or CHECK_ERROR (FAILED), RUN_DEADLINE or RUN_STOPPED (SKIPPED).
-- 75072 the run is not running, 75073 a row number outside the file, 75074 a ledger row that is not this row's check,
-- 75079 an unknown reason, 75030 a caller who cannot read the ledger's verdicts.
CREATE OR REPLACE PROCEDURE ASOF.ADD_BACKTEST_ITEM (
    IN  P_RUN_ID     BIGINT,
    IN  P_ROW_NO     SMALLINT,
    IN  P_DATE       DATE,
    IN  P_CHANNEL    VARCHAR(20),
    IN  P_DOC_ID     VARCHAR(32),     -- '' when no document was checked against
    IN  P_LEDGER_ID  BIGINT,          -- 0 when no decision was recorded
    IN  P_REASON     VARCHAR(40),     -- only read without a ledger row
    IN  P_DETAIL     VARCHAR(300),
    OUT P_OUTCOME    VARCHAR(12))
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  DECLARE V_STATUS VARCHAR(12);
  DECLARE V_ROWS SMALLINT;
  DECLARE V_CHANNEL VARCHAR(20);
  DECLARE V_AS_OF DATE;
  DECLARE V_DOC VARCHAR(32);
  DECLARE V_DECISION VARCHAR(12);
  DECLARE V_REASON VARCHAR(40);
  DECLARE V_VERDICTS VARCHAR(30000);
  DECLARE V_CONTRADICTED INTEGER;

  IF VERIFY_ROLE_FOR_USER(SESSION_USER, 'ASOF_TEXT_READER') <> 1 THEN
    SIGNAL SQLSTATE '75030' SET MESSAGE_TEXT = 'ADD_BACKTEST_ITEM needs role ASOF_TEXT_READER: it reads the ledger verdicts';
  END IF;
  SELECT STATUS, ROW_COUNT INTO V_STATUS, V_ROWS FROM ASOF.BACKTEST_RUN WHERE RUN_ID = P_RUN_ID;
  IF V_STATUS IS NULL OR V_STATUS <> 'RUNNING' THEN
    SIGNAL SQLSTATE '75072' SET MESSAGE_TEXT = 'That backtest run is not running';
  END IF;
  IF P_ROW_NO IS NULL OR P_ROW_NO NOT BETWEEN 1 AND V_ROWS THEN
    SIGNAL SQLSTATE '75073' SET MESSAGE_TEXT = 'That row number is outside the backtest file';
  END IF;

  IF COALESCE(P_LEDGER_ID, 0) = 0 THEN
    SET V_REASON = P_REASON;
    SET P_OUTCOME = CASE WHEN P_REASON IN ('LEDGER_UNAVAILABLE', 'CHECK_ERROR') THEN 'FAILED'
                         WHEN P_REASON IN ('RUN_DEADLINE', 'RUN_STOPPED') THEN 'SKIPPED' END;
    IF P_OUTCOME IS NULL THEN
      SIGNAL SQLSTATE '75079' SET MESSAGE_TEXT = 'A row without a ledger decision needs a known reason';
    END IF;
  ELSE
    SELECT CHANNEL, AS_OF_DATE, DOC_ID, DECISION, REASON_CODE, VERDICTS_JSON
      INTO V_CHANNEL, V_AS_OF, V_DOC, V_DECISION, V_REASON, V_VERDICTS
      FROM ASOF.ANSWER_LEDGER WHERE LEDGER_ID = P_LEDGER_ID;
    IF V_CHANNEL IS NULL OR V_CHANNEL <> 'backtest' OR V_AS_OF <> P_DATE OR V_DOC <> P_DOC_ID
       OR COALESCE(JSON_VALUE(V_VERDICTS, '$.backtest.run_id' RETURNING BIGINT), 0) <> P_RUN_ID
       OR COALESCE(JSON_VALUE(V_VERDICTS, '$.backtest.row' RETURNING INTEGER), 0) <> P_ROW_NO
       OR COALESCE(JSON_VALUE(V_VERDICTS, '$.backtest.source_channel' RETURNING VARCHAR(20)), '') <> P_CHANNEL THEN
      SIGNAL SQLSTATE '75074' SET MESSAGE_TEXT = 'That ledger decision is not this run''s check of this row';
    END IF;
    SET V_CONTRADICTED = (SELECT COUNT(*) FROM ASOF.CLAIM_CITATION C
                          WHERE C.LEDGER_ID = P_LEDGER_ID AND C.PASS_NO = 1 AND C.VERDICT = 'CONTRADICTED');
    SET P_OUTCOME = CASE
      WHEN V_CONTRADICTED > 0 THEN 'WRONG'
      WHEN V_REASON IN ('ERROR_FAIL_CLOSED', 'LEDGER_UNAVAILABLE') THEN 'FAILED'
      WHEN V_DECISION = 'PASS' THEN 'OK'
      ELSE 'UNCONFIRMED' END;
  END IF;

  INSERT INTO ASOF.BACKTEST_ITEM (RUN_ID, ROW_NO, CUSTOMER_DATE, SOURCE_CHANNEL, DOC_ID, LEDGER_ID, OUTCOME,
                                  REASON_CODE, DETAIL)
    VALUES (P_RUN_ID, P_ROW_NO, P_DATE, P_CHANNEL, NULLIF(P_DOC_ID, ''), NULLIF(P_LEDGER_ID, 0), P_OUTCOME, V_REASON,
            NULLIF(TRIM(COALESCE(P_DETAIL, '')), ''));
  UPDATE ASOF.BACKTEST_RUN SET LAST_PROGRESS_AT = CURRENT TIMESTAMP WHERE RUN_ID = P_RUN_ID;
END
@

-- procedure: ADD_BACKTEST_COST
-- The money a contradicted claim of a WRONG item put at stake, or why there is none to compute. The clause version is
-- read from the claim's citation, never from the caller; with a rule key, Db2 reads the amount from that exact clause
-- row's RULE_JSON (JSON_VALUE) and stores the difference. P_RULE_KEY '' means not computable, with P_NOTE saying why.
-- 75075 the row is not a WRONG item of a running run, 75076 the claim is not a contradicted first-pass claim with a
-- clause, 75077 a key that is not a plain *_usd key, a clause version without a number under it, or an amount out of
-- range.
CREATE OR REPLACE PROCEDURE ASOF.ADD_BACKTEST_COST (
    IN  P_RUN_ID    BIGINT,
    IN  P_ROW_NO    SMALLINT,
    IN  P_CLAIM_NO  SMALLINT,
    IN  P_RULE_KEY  VARCHAR(64),
    IN  P_STATED    DECIMAL(11, 2),
    IN  P_NOTE      VARCHAR(200),
    OUT P_POLICY    DECIMAL(11, 2))
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  DECLARE V_LEDGER BIGINT;
  DECLARE V_CLAUSE VARCHAR(32);
  DECLARE V_VERSION VARCHAR(20);
  DECLARE V_BUS_START DATE;
  DECLARE V_SYS_START TIMESTAMP(12);
  DECLARE V_RULE VARCHAR(2000);
  DECLARE V_RAW VARCHAR(40);
  DECLARE V_KEY VARCHAR(64);
  DECLARE V_FAVOURS VARCHAR(10);

  SET P_POLICY = 0;
  SELECT I.LEDGER_ID INTO V_LEDGER
    FROM ASOF.BACKTEST_ITEM I JOIN ASOF.BACKTEST_RUN R ON R.RUN_ID = I.RUN_ID
    WHERE I.RUN_ID = P_RUN_ID AND I.ROW_NO = P_ROW_NO AND I.OUTCOME = 'WRONG' AND R.STATUS = 'RUNNING';
  IF V_LEDGER IS NULL THEN
    SIGNAL SQLSTATE '75075' SET MESSAGE_TEXT = 'Money is recorded only for a wrong answer of a running backtest';
  END IF;
  SELECT CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START INTO V_CLAUSE, V_VERSION, V_BUS_START, V_SYS_START
    FROM ASOF.CLAIM_CITATION
    WHERE LEDGER_ID = V_LEDGER AND PASS_NO = 1 AND CLAIM_NO = P_CLAIM_NO AND VERDICT = 'CONTRADICTED';
  IF V_CLAUSE IS NULL THEN
    SIGNAL SQLSTATE '75076' SET MESSAGE_TEXT = 'That claim is not a contradicted claim of this answer';
  END IF;

  SET V_KEY = NULLIF(TRIM(COALESCE(P_RULE_KEY, '')), '');
  IF V_KEY IS NULL THEN
    IF LENGTH(TRIM(COALESCE(P_NOTE, ''))) < 10 THEN
      SIGNAL SQLSTATE '75077' SET MESSAGE_TEXT = 'Say why the money difference cannot be computed';
    END IF;
    INSERT INTO ASOF.BACKTEST_COST (RUN_ID, ROW_NO, CLAIM_NO, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, STATUS, NOTE)
      VALUES (P_RUN_ID, P_ROW_NO, P_CLAIM_NO, V_CLAUSE, V_VERSION, V_BUS_START, 'NOT_COMPUTABLE', P_NOTE);
    RETURN;
  END IF;

  -- Only a plain lower-case key ending in _usd may become part of the JSON path; limits (max_, min_) are not amounts.
  IF TRANSLATE(V_KEY, '', 'abcdefghijklmnopqrstuvwxyz0123456789_') <> '' OR V_KEY NOT LIKE '%\_usd' ESCAPE '\'
     OR V_KEY LIKE 'max\_%' ESCAPE '\' OR V_KEY LIKE 'min\_%' ESCAPE '\'
     OR P_STATED IS NULL OR P_STATED < 0 OR P_STATED > 1000000 THEN
    SIGNAL SQLSTATE '75077' SET MESSAGE_TEXT = 'A money difference needs a dollar amount key and a stated amount from 0 to 1,000,000';
  END IF;
  -- The exact clause row the claim was checked against, current or superseded since.
  SET V_RULE = (SELECT RULE_JSON FROM ASOF.POLICY_CLAUSE FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30'
                WHERE CLAUSE_ID = V_CLAUSE AND BUS_START = V_BUS_START AND SYS_START = V_SYS_START);
  SET V_RAW = JSON_VALUE(V_RULE, '$.' || V_KEY RETURNING VARCHAR(40) NULL ON ERROR);
  IF V_RAW IS NULL OR V_RAW IN ('true', 'false') OR TRANSLATE(V_RAW, '', '0123456789.') <> '' THEN
    SIGNAL SQLSTATE '75077' SET MESSAGE_TEXT = 'The cited clause version sets no dollar amount under that key';
  END IF;
  SET P_POLICY = JSON_VALUE(V_RULE, '$.' || V_KEY RETURNING DECIMAL(11, 2));
  SET V_FAVOURS = CASE WHEN P_STATED = P_POLICY THEN NULL
                       WHEN LOCATE('fee', V_KEY) > 0 THEN CASE WHEN P_STATED < P_POLICY THEN 'CUSTOMER' ELSE 'COMPANY' END
                       ELSE CASE WHEN P_STATED > P_POLICY THEN 'CUSTOMER' ELSE 'COMPANY' END END;
  INSERT INTO ASOF.BACKTEST_COST (RUN_ID, ROW_NO, CLAIM_NO, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, STATUS,
                                  RULE_KEY, STATED_USD, POLICY_USD, DIFF_USD, FAVOURS, NOTE)
    VALUES (P_RUN_ID, P_ROW_NO, P_CLAIM_NO, V_CLAUSE, V_VERSION, V_BUS_START, 'COMPUTED', V_KEY, P_STATED, P_POLICY,
            P_STATED - P_POLICY, V_FAVOURS, COALESCE(NULLIF(TRIM(COALESCE(P_NOTE, '')), ''), 'one occurrence'));
END
@

-- procedure: FINISH_BACKTEST
-- Closes a run, once. DONE, DEADLINE and STOPPED need an outcome for every row of the file (the rows a deadline or a
-- stop left unchecked are SKIPPED items), so a finished run accounts for every row. FAILED (the runner itself could not
-- go on) may leave rows without one; the report counts them. 75072 not running, 75078 rows unaccounted for, 75079 an
-- unknown status.
CREATE OR REPLACE PROCEDURE ASOF.FINISH_BACKTEST (
    IN P_RUN_ID BIGINT,
    IN P_STATUS VARCHAR(12),
    IN P_NOTE   VARCHAR(400))
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  DECLARE V_STATUS VARCHAR(12);
  DECLARE V_ROWS SMALLINT;
  DECLARE V_ITEMS INTEGER;

  SELECT STATUS, ROW_COUNT INTO V_STATUS, V_ROWS FROM ASOF.BACKTEST_RUN WHERE RUN_ID = P_RUN_ID;
  IF V_STATUS IS NULL OR V_STATUS <> 'RUNNING' THEN
    SIGNAL SQLSTATE '75072' SET MESSAGE_TEXT = 'That backtest run is not running';
  END IF;
  IF P_STATUS IS NULL OR P_STATUS NOT IN ('DONE', 'DEADLINE', 'STOPPED', 'FAILED') THEN
    SIGNAL SQLSTATE '75079' SET MESSAGE_TEXT = 'A backtest run ends DONE, DEADLINE, STOPPED or FAILED';
  END IF;
  SET V_ITEMS = (SELECT COUNT(*) FROM ASOF.BACKTEST_ITEM WHERE RUN_ID = P_RUN_ID);
  IF P_STATUS <> 'FAILED' AND V_ITEMS <> V_ROWS THEN
    SIGNAL SQLSTATE '75078' SET MESSAGE_TEXT = 'A backtest run ends only when every row has an outcome';
  END IF;
  UPDATE ASOF.BACKTEST_RUN SET STATUS = P_STATUS, NOTE = NULLIF(TRIM(COALESCE(P_NOTE, '')), ''),
                               FINISHED_AT = CURRENT TIMESTAMP, LAST_PROGRESS_AT = CURRENT TIMESTAMP
    WHERE RUN_ID = P_RUN_ID;
END
@

-- view: V_BACKTEST_RUNS
-- Every run with its outcome counts. STATE is STATUS, except that a run still marked RUNNING with no progress for
-- STALE_AFTER_S seconds is INTERRUPTED: the process running it stopped, and its remaining rows were never checked.
CREATE OR REPLACE VIEW ASOF.V_BACKTEST_RUNS AS
  SELECT R.RUN_ID, R.SOURCE_NAME, R.SOURCE_SHA256, R.ROW_COUNT, R.DOC_ID, R.MODEL_INFO, R.IS_SAMPLE,
         CASE WHEN R.STATUS = 'RUNNING' AND CURRENT TIMESTAMP > R.LAST_PROGRESS_AT + R.STALE_AFTER_S SECONDS
              THEN 'INTERRUPTED' ELSE R.STATUS END AS STATE,
         R.NOTE, R.CREATED_AT, R.CREATED_BY, R.REQUESTED_BY, R.DEADLINE_AT, R.LAST_PROGRESS_AT, R.FINISHED_AT,
         COALESCE(I.ITEMS, 0) AS ITEMS, COALESCE(I.WRONG, 0) AS WRONG, COALESCE(I.UNCONFIRMED, 0) AS UNCONFIRMED,
         COALESCE(I.OK, 0) AS OK, COALESCE(I.FAILED, 0) AS FAILED, COALESCE(I.SKIPPED, 0) AS SKIPPED
  FROM ASOF.BACKTEST_RUN R
  LEFT JOIN (SELECT RUN_ID, COUNT(*) AS ITEMS,
                    SUM(CASE WHEN OUTCOME = 'WRONG' THEN 1 ELSE 0 END) AS WRONG,
                    SUM(CASE WHEN OUTCOME = 'UNCONFIRMED' THEN 1 ELSE 0 END) AS UNCONFIRMED,
                    SUM(CASE WHEN OUTCOME = 'OK' THEN 1 ELSE 0 END) AS OK,
                    SUM(CASE WHEN OUTCOME = 'FAILED' THEN 1 ELSE 0 END) AS FAILED,
                    SUM(CASE WHEN OUTCOME = 'SKIPPED' THEN 1 ELSE 0 END) AS SKIPPED
             FROM ASOF.BACKTEST_ITEM GROUP BY RUN_ID) I ON I.RUN_ID = R.RUN_ID
@

-- view: V_BACKTEST_CONTRADICTIONS
-- One row per contradicted first-pass claim of a wrong answer: the clause version it contradicted (with that row's
-- business period, current or superseded since) and the money difference if one was computed. No ledger free text.
CREATE OR REPLACE VIEW ASOF.V_BACKTEST_CONTRADICTIONS AS
  SELECT I.RUN_ID, I.ROW_NO, I.LEDGER_ID, I.CUSTOMER_DATE, I.SOURCE_CHANNEL, I.DOC_ID, C.CLAIM_NO, C.AREA,
         C.CLAIM_TEXT, C.RULE_CHECK, C.CLAUSE_ID, C.CLAUSE_VERSION, C.CLAUSE_BUS_START, P.BUS_END AS CLAUSE_BUS_END,
         K.STATUS AS COST_STATUS, K.RULE_KEY, K.STATED_USD, K.POLICY_USD, K.DIFF_USD, K.FAVOURS, K.NOTE AS COST_NOTE
  FROM ASOF.BACKTEST_ITEM I
  JOIN ASOF.CLAIM_CITATION C ON C.LEDGER_ID = I.LEDGER_ID AND C.PASS_NO = 1 AND C.VERDICT = 'CONTRADICTED'
  LEFT JOIN ASOF.POLICY_CLAUSE FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30' AS P
    ON P.CLAUSE_ID = C.CLAUSE_ID AND P.BUS_START = C.CLAUSE_BUS_START AND P.SYS_START = C.CLAUSE_SYS_START
  LEFT JOIN ASOF.BACKTEST_COST K ON K.RUN_ID = I.RUN_ID AND K.ROW_NO = I.ROW_NO AND K.CLAIM_NO = C.CLAIM_NO
  WHERE I.OUTCOME = 'WRONG'
@
