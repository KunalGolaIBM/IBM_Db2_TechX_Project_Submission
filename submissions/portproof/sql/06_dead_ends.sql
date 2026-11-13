-- What the model has already failed at, so it is not paid to fail again.
-- Run as the schema owner. Statements are separated by a line containing only --@
-- Db2 Community Edition 12.1.5.0

DROP PROCEDURE PORTPROOF.RECORD_DEAD_END
--@
DROP TABLE PORTPROOF.MODEL_DEAD_END
--@
-- One row per question a model was asked in full and could not answer: every
-- attempt it was allowed came back, and every one was rejected by Db2 or
-- disproved by the differential proof. SUBJECT_SHA is a hash of the question
-- itself (dialect, source SQL, Db2 SQL), so a statement that changes is a new
-- question. A call that timed out or hit the budget is not recorded, because
-- that says nothing about whether the model could have answered.
CREATE TABLE PORTPROOF.MODEL_DEAD_END (
  SUBJECT_SHA VARCHAR(64) NOT NULL,
  STAGE       VARCHAR(20) NOT NULL,
  MODEL       VARCHAR(80) NOT NULL,
  CASE_NAME   VARCHAR(80),
  ATTEMPTS    INTEGER     NOT NULL DEFAULT 1,
  CREATED_AT  TIMESTAMP   NOT NULL DEFAULT CURRENT TIMESTAMP,
  CONSTRAINT PK_DEAD_END PRIMARY KEY (SUBJECT_SHA, STAGE, MODEL),
  CONSTRAINT CK_DEAD_STAGE CHECK (STAGE IN ('SEMANTIC_REPAIR', 'DATASET')),
  CONSTRAINT CK_DEAD_ATTEMPTS CHECK (ATTEMPTS >= 1)
)
--@
CREATE PROCEDURE PORTPROOF.RECORD_DEAD_END (
  IN P_SHA      VARCHAR(64),
  IN P_STAGE    VARCHAR(20),
  IN P_MODEL    VARCHAR(80),
  IN P_CASE     VARCHAR(80),
  IN P_ATTEMPTS INTEGER
)
LANGUAGE SQL
MODIFIES SQL DATA
BEGIN
  MERGE INTO PORTPROOF.MODEL_DEAD_END AS t
  USING (VALUES (P_SHA, P_STAGE, P_MODEL)) AS s (SUBJECT_SHA, STAGE, MODEL)
     ON t.SUBJECT_SHA = s.SUBJECT_SHA AND t.STAGE = s.STAGE AND t.MODEL = s.MODEL
  WHEN MATCHED THEN
    UPDATE SET ATTEMPTS = t.ATTEMPTS + COALESCE(P_ATTEMPTS, 1), CREATED_AT = CURRENT TIMESTAMP
  WHEN NOT MATCHED THEN
    INSERT (SUBJECT_SHA, STAGE, MODEL, CASE_NAME, ATTEMPTS)
    VALUES (P_SHA, P_STAGE, P_MODEL, P_CASE, COALESCE(P_ATTEMPTS, 1));
END
--@
GRANT SELECT ON PORTPROOF.MODEL_DEAD_END TO USER PPAPP
--@
GRANT EXECUTE ON PROCEDURE PORTPROOF.RECORD_DEAD_END TO USER PPAPP
