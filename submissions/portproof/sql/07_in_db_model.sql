-- The model tier, called from inside Db2.
-- Applied by `python -m src.setup_model`, after it has registered the external
-- model PORTPROOF.PP_MODEL, because ASK_MODEL is compiled against that model.
-- Run as the schema owner. Statements are separated by a line containing only --@
-- Db2 12.1.5.0 or later (CREATE EXTERNAL MODEL, TEXT_GENERATION)

-- Which road a call took, and whether its token counts are the provider's own
-- or an estimate. Db2's TEXT_GENERATION returns the text and no usage, so a
-- call made in the engine is metered as characters / 4 and marked as such.
ALTER TABLE PORTPROOF.LLM_CALL ADD COLUMN TRANSPORT VARCHAR(8) NOT NULL DEFAULT 'HTTP'
--@
ALTER TABLE PORTPROOF.LLM_CALL ADD COLUMN ESTIMATED SMALLINT NOT NULL DEFAULT 0
--@
DROP PROCEDURE PORTPROOF.ASK_MODEL
--@
-- One model call, made and ledgered by the engine in the same procedure.
--
-- The runtime identity holds no USAGE on the external model: the only way it
-- can reach a model is this procedure, and this procedure cannot return an
-- answer without writing the ledger row first. So "every model call is
-- recorded" is not a convention the application follows. It is the only path
-- that exists. The API key lives in Db2's catalogue, is supplied once by the
-- owner, and is never held by the application or returned by a catalogue view.
--
-- P_BUDGET is the caller's ceiling on calls since P_SINCE. The engine counts
-- its own ledger and refuses with SQLSTATE 75002 when it is reached.
CREATE PROCEDURE PORTPROOF.ASK_MODEL (
  IN  P_STAGE  VARCHAR(20),
  IN  P_CASE   VARCHAR(80),
  IN  P_PROMPT CLOB(32K),
  IN  P_SINCE  TIMESTAMP,
  IN  P_BUDGET INTEGER,
  OUT P_REPLY  CLOB(32K)
)
LANGUAGE SQL
MODIFIES SQL DATA
BEGIN
  DECLARE V_STARTED TIMESTAMP;
  DECLARE V_MODEL VARCHAR(80);
  DECLARE V_SPENT INTEGER;
  DECLARE V_MS INTEGER;

  SET V_SPENT = (SELECT COUNT(*) FROM PORTPROOF.LLM_CALL
                  WHERE CREATED_AT >= COALESCE(P_SINCE, CURRENT TIMESTAMP - 1 DAY));
  IF P_BUDGET IS NOT NULL AND V_SPENT >= P_BUDGET THEN
    SIGNAL SQLSTATE '75002' SET MESSAGE_TEXT = 'model call budget is spent';
  END IF;

  SET V_MODEL = COALESCE(
    (SELECT MODELID FROM SYSCAT.EXTERNALMODELS
      WHERE MODELSCHEMA = 'PORTPROOF' AND MODELNAME = 'PP_MODEL'), 'PP_MODEL');
  SET V_STARTED = CURRENT TIMESTAMP;
  SET P_REPLY = TEXT_GENERATION(P_PROMPT USING PORTPROOF.PP_MODEL);
  SET V_MS = INTEGER(TIMESTAMPDIFF(1, CHAR(CURRENT TIMESTAMP - V_STARTED)) / 1000);

  INSERT INTO PORTPROOF.LLM_CALL
         (STAGE, MODEL, CASE_NAME, PROMPT_TOKENS, COMPLETION_TOKENS, LATENCY_MS, OK,
          TRANSPORT, ESTIMATED)
  VALUES (P_STAGE, V_MODEL, P_CASE, LENGTH(P_PROMPT) / 4, COALESCE(LENGTH(P_REPLY), 0) / 4,
          COALESCE(V_MS, 0), CASE WHEN P_REPLY IS NULL THEN 0 ELSE 1 END, 'DB2', 1);
END
--@
GRANT EXECUTE ON PROCEDURE PORTPROOF.ASK_MODEL TO USER PPAPP
