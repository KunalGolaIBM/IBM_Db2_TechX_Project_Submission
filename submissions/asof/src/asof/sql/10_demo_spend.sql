-- The public demo's daily budget for live checks (ASOF_PUBLIC_DEMO=true with ASOF_DEMO_LIVE=true; asof/demolive.py).
-- One row per UTC day. The runtime user reads it and changes it only through the two procedures below; nobody holds
-- INSERT, UPDATE or DELETE on it (90_grants.sql). Every other install has the table too, and it stays empty.

-- table: DEMO_SPEND
-- CHECKS_USED counts live checks admitted on the day; DAILY_CAP is the cap in force at the latest admission, so
-- CK_DEMO_SPEND_UNDER_CAP holds a day to at most its cap. The LLM calls and tokens are what the provider reported
-- for those checks (0 where it reports none).
CREATE TABLE ASOF.DEMO_SPEND (
  SPEND_DAY     DATE      NOT NULL,
  CHECKS_USED   INTEGER   NOT NULL DEFAULT 0,
  DAILY_CAP     INTEGER   NOT NULL DEFAULT 0,
  LLM_CALLS     INTEGER   NOT NULL DEFAULT 0,
  INPUT_TOKENS  BIGINT    NOT NULL DEFAULT 0,
  OUTPUT_TOKENS BIGINT    NOT NULL DEFAULT 0,
  UPDATED_AT    TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
  CONSTRAINT PK_DEMO_SPEND PRIMARY KEY (SPEND_DAY),
  CONSTRAINT CK_DEMO_SPEND_COUNTS CHECK (CHECKS_USED >= 0 AND DAILY_CAP >= 0 AND LLM_CALLS >= 0
                                         AND INPUT_TOKENS >= 0 AND OUTPUT_TOKENS >= 0),
  CONSTRAINT CK_DEMO_SPEND_UNDER_CAP CHECK (CHECKS_USED <= DAILY_CAP)
) IN ASOF_TS32K
@

-- procedure: CLAIM_DEMO_CHECK
-- Admits one live check against the day's cap, or refuses it with SQLSTATE 75097. The day is Db2's own UTC date,
-- never the caller's. The first UPDATE takes the day row's exclusive lock before the count is read, so concurrent
-- callers queue on that lock and each reads the count the previous one committed: two sessions racing at the cap
-- cannot both pass. A caller waits at most its CURRENT LOCK TIMEOUT (the runtime user's is DB2_LOCK_TIMEOUT_S).
-- The caller commits, or rolls back after a refusal.
CREATE OR REPLACE PROCEDURE ASOF.CLAIM_DEMO_CHECK (
    IN  P_CAP  INTEGER,
    OUT P_DAY  DATE,
    OUT P_USED INTEGER)
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  DECLARE V_USED INTEGER;
  DECLARE V_RACED SMALLINT DEFAULT 0;

  IF P_CAP IS NULL OR P_CAP < 1 OR P_CAP > 100000 THEN
    SIGNAL SQLSTATE '75098' SET MESSAGE_TEXT = 'The daily cap must be 1 to 100000 live checks';
  END IF;
  SET P_DAY = DATE(CURRENT TIMESTAMP - CURRENT TIMEZONE);
  BEGIN
    -- Two first callers of a day may both find no row; the second insert then fails on the key and is ignored.
    DECLARE CONTINUE HANDLER FOR SQLSTATE '23505' SET V_RACED = 1;
    INSERT INTO ASOF.DEMO_SPEND (SPEND_DAY)
      SELECT P_DAY FROM SYSIBM.SYSDUMMY1 WHERE NOT EXISTS (SELECT 1 FROM ASOF.DEMO_SPEND WHERE SPEND_DAY = P_DAY);
  END;
  UPDATE ASOF.DEMO_SPEND SET UPDATED_AT = CURRENT TIMESTAMP WHERE SPEND_DAY = P_DAY;
  SET V_USED = (SELECT CHECKS_USED FROM ASOF.DEMO_SPEND WHERE SPEND_DAY = P_DAY);
  IF V_USED IS NULL THEN
    SIGNAL SQLSTATE '75098' SET MESSAGE_TEXT = 'The spend row for this day is missing';
  END IF;
  IF V_USED >= P_CAP THEN
    SIGNAL SQLSTATE '75097' SET MESSAGE_TEXT = 'The cap on live checks for this day is reached';
  END IF;
  UPDATE ASOF.DEMO_SPEND SET CHECKS_USED = CHECKS_USED + 1, DAILY_CAP = P_CAP WHERE SPEND_DAY = P_DAY;
  SET P_USED = V_USED + 1;
END
@

-- procedure: RECORD_DEMO_SPEND
-- Adds what an admitted check used (model calls and the tokens the provider reported) to the day it was admitted on.
-- Refuses (75098) a day with no admitted check, negative values and values no single check reaches.
CREATE OR REPLACE PROCEDURE ASOF.RECORD_DEMO_SPEND (
    IN P_DAY           DATE,
    IN P_CALLS         INTEGER,
    IN P_INPUT_TOKENS  BIGINT,
    IN P_OUTPUT_TOKENS BIGINT)
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  DECLARE V_ROWS INTEGER;

  IF P_DAY IS NULL OR P_CALLS IS NULL OR P_INPUT_TOKENS IS NULL OR P_OUTPUT_TOKENS IS NULL
     OR P_CALLS < 0 OR P_CALLS > 100 OR P_INPUT_TOKENS < 0 OR P_INPUT_TOKENS > 10000000
     OR P_OUTPUT_TOKENS < 0 OR P_OUTPUT_TOKENS > 1000000 THEN
    SIGNAL SQLSTATE '75098' SET MESSAGE_TEXT = 'The usage of one live check must be 0 to 100 calls and a bounded token count';
  END IF;
  UPDATE ASOF.DEMO_SPEND
     SET LLM_CALLS = LLM_CALLS + P_CALLS, INPUT_TOKENS = INPUT_TOKENS + P_INPUT_TOKENS,
         OUTPUT_TOKENS = OUTPUT_TOKENS + P_OUTPUT_TOKENS, UPDATED_AT = CURRENT TIMESTAMP
   WHERE SPEND_DAY = P_DAY AND CHECKS_USED > 0;
  GET DIAGNOSTICS V_ROWS = ROW_COUNT;
  IF V_ROWS = 0 THEN
    SIGNAL SQLSTATE '75098' SET MESSAGE_TEXT = 'No live check was admitted on that day';
  END IF;
END
@
