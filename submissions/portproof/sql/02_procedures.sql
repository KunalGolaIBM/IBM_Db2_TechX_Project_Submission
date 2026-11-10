-- SQL PL procedures. The runtime user cannot INSERT into the ledger directly; it
-- may only CALL these, so every write is validated and shaped by the engine.
-- Statements are separated by a line containing only --@

DROP PROCEDURE PORTPROOF.RECORD_TRANSLATION
--@
DROP PROCEDURE PORTPROOF.RECORD_VERDICT
--@
DROP PROCEDURE PORTPROOF.ESCALATE_STALLED
--@
-- Upsert a statement's translation state, idempotent per case name.
--
-- This is a real MERGE, and it used to be a SELECT followed by an IF/INSERT or
-- ELSE/UPDATE. That is a read-then-write race: two concurrent runs of the same
-- case both read NULL and both INSERT, and the second one fails on
-- UQ_STATEMENT_CASE rather than updating. MERGE decides matched/not-matched
-- inside the engine, in one statement, under one set of locks.
CREATE PROCEDURE PORTPROOF.RECORD_TRANSLATION (
  IN  P_CASE     VARCHAR(80),
  IN  P_DIALECT  VARCHAR(16),
  IN  P_SRC      VARCHAR(4000),
  IN  P_DB2      VARCHAR(4000),
  IN  P_STATUS   VARCHAR(24),
  IN  P_SQLCODE  INTEGER,
  IN  P_ERROR    VARCHAR(1200),
  IN  P_META     VARCHAR(2000),
  -- How many times the repair loop actually asked Db2 about this statement.
  -- It used to be derived in here as "number of times this row was written",
  -- which counts *runs of PortProof*, not repair attempts -- so the escalation
  -- threshold below was measuring the wrong thing entirely.
  IN  P_ATTEMPTS SMALLINT,
  OUT P_STMT_ID  INTEGER
)
LANGUAGE SQL
MODIFIES SQL DATA
BEGIN
  MERGE INTO PORTPROOF.STATEMENT AS T
  USING (VALUES (P_CASE, P_DIALECT, P_SRC, P_DB2, P_STATUS, P_SQLCODE, P_ERROR,
                 P_META, LEAST(COALESCE(P_ATTEMPTS, 0), 10)))
     AS S (CASE_NAME, SRC_DIALECT, SRC_SQL, DB2_SQL, STATUS, LAST_SQLCODE,
           LAST_ERROR, META, ATTEMPTS)
     ON T.CASE_NAME = S.CASE_NAME
  WHEN MATCHED THEN
    UPDATE SET DB2_SQL      = S.DB2_SQL,
               STATUS       = S.STATUS,
               ATTEMPTS     = S.ATTEMPTS,
               LAST_SQLCODE = S.LAST_SQLCODE,
               LAST_ERROR   = S.LAST_ERROR,
               META         = COALESCE(S.META, T.META)
  WHEN NOT MATCHED THEN
    INSERT (CASE_NAME, SRC_DIALECT, SRC_SQL, DB2_SQL, STATUS, ATTEMPTS,
            LAST_SQLCODE, LAST_ERROR, META)
    VALUES (S.CASE_NAME, S.SRC_DIALECT, S.SRC_SQL, S.DB2_SQL, S.STATUS,
            S.ATTEMPTS, S.LAST_SQLCODE, S.LAST_ERROR, S.META);

  -- The identity is read back rather than taken from IDENTITY_VAL_LOCAL(),
  -- which is only set by an INSERT and would be stale on the MATCHED path.
  SET P_STMT_ID = (SELECT STMT_ID FROM PORTPROOF.STATEMENT WHERE CASE_NAME = P_CASE);
END
--@
-- Record a proof. Db2 computes the SHA-256 certificate hash itself, so the
-- application cannot forge or backdate a verdict.
CREATE PROCEDURE PORTPROOF.RECORD_VERDICT (
  IN  P_STMT_ID    INTEGER,
  IN  P_KIND       VARCHAR(16),
  IN  P_OUTCOME    VARCHAR(24),
  IN  P_INSTANCES  SMALLINT,
  IN  P_DETAIL     VARCHAR(8000),
  OUT P_CERT_SHA   VARCHAR(64)
)
LANGUAGE SQL
MODIFIES SQL DATA
BEGIN
  DECLARE V_SHA VARCHAR(64);

  -- SHA-256 over the verdict's identifying content, computed in-engine.
  SET V_SHA = LOWER(HEX(HASH(
        CAST(P_STMT_ID AS VARCHAR(12)) || '|' || P_KIND || '|' || P_OUTCOME || '|' ||
        CAST(COALESCE(P_INSTANCES, 0) AS VARCHAR(8)) || '|' ||
        COALESCE(P_DETAIL, '') || '|' ||
        CAST(CURRENT TIMESTAMP AS VARCHAR(32)), 2)));

  INSERT INTO PORTPROOF.VERDICT (STMT_ID, KIND, OUTCOME, INSTANCES, DETAIL, CERT_SHA)
  VALUES (P_STMT_ID, P_KIND, P_OUTCOME, COALESCE(P_INSTANCES, 0), P_DETAIL, V_SHA);

  SET P_CERT_SHA = V_SHA;
END
--@
-- Any statement that burned its repair budget without a proof is escalated to a
-- human. A cursor with an explicit handler, so the loop is bounded and auditable.
--
-- It also records *why* each one stalled, in the one place a reviewer will look:
-- the statement's own LAST_ERROR. An ESCALATED row that still carries the raw
-- SQLCODE and nothing else tells a human what failed but not that the machine
-- has given up on it.
CREATE PROCEDURE PORTPROOF.ESCALATE_STALLED (
  IN  P_MAX_ATTEMPTS SMALLINT,
  OUT P_ESCALATED    INTEGER
)
LANGUAGE SQL
MODIFIES SQL DATA
BEGIN
  DECLARE V_ID    INTEGER;
  DECLARE V_DONE  SMALLINT DEFAULT 0;
  DECLARE V_COUNT INTEGER  DEFAULT 0;

  DECLARE C_STALLED CURSOR FOR
    SELECT STMT_ID FROM PORTPROOF.STATEMENT
     WHERE ATTEMPTS >= P_MAX_ATTEMPTS
       AND STATUS IN ('COMPILE_FAIL', 'TRANSLATE_FAIL', 'PROVEN_DIFFERENT');

  DECLARE CONTINUE HANDLER FOR NOT FOUND SET V_DONE = 1;

  OPEN C_STALLED;
  FETCH C_STALLED INTO V_ID;
  WHILE V_DONE = 0 DO
    UPDATE PORTPROOF.STATEMENT
       SET STATUS     = 'ESCALATED',
           LAST_ERROR = SUBSTR('escalated for human review after ' ||
                               CAST(ATTEMPTS AS VARCHAR(4)) ||
                               ' attempt(s); last: ' || COALESCE(LAST_ERROR, ''),
                               1, 1200)
     WHERE STMT_ID = V_ID;
    SET V_COUNT = V_COUNT + 1;
    FETCH C_STALLED INTO V_ID;
  END WHILE;
  CLOSE C_STALLED;

  SET P_ESCALATED = V_COUNT;
END
