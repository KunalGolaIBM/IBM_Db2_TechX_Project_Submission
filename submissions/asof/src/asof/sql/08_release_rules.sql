-- Release rules: Db2 itself refuses to record a released answer that the policy in force does not back.
-- The Python check decides PASS, CORRECTED or ESCALATED; these rules make Db2 refuse to store a PASS or a
-- CORRECTED row unless every claim the customer is given (the draft's claims for a PASS, the re-checked
-- rewrite's claims for a CORRECTED answer) is SUPPORTED and cites a clause version that
--   1. was in force on the row's AS_OF_DATE, in the row's policy document (FOR BUSINESS_TIME AS OF), and
--   2. contains the claim's quoted span in its text (case, spacing, curly quotes and end punctuation aside).
-- The claims are read from VERDICTS_JSON, the document that is hashed into the chain, with JSON_TABLE
-- (CLAIMS_FROM_JSON in 03_procedures.sql: Db2 12.1 takes only 'strict $' as a JSON_TABLE row path, so each
-- array position is read with a literal index). A BEFORE INSERT trigger enforces this on every insert into
-- ANSWER_LEDGER, by any user, the owner included, so APPEND_LEDGER and a direct INSERT are refused alike:
--   75080 a released claim is not SUPPORTED, or names no clause
--   75081 a released claim cites a clause version not in force on the customer's date (or in another document)
--   75082 a released claim's quote is missing, shorter than 12 characters, or not in the cited version's text
--   75083 the claims do not have the shape the decision needs: a PASS carries only the draft's check, a CORRECTED
--         answer must carry the re-check of its rewrite, and every entry must be a readable claim
--   75003 more than 16 claim entries (8 per check), as APPEND_LEDGER_ROW refuses
-- ESCALATED rows (a holding reply) and REVIEWED rows (RESOLVE_ESCALATION enforces its own rules) are not
-- affected. The gate treats a refusal as a held decision: it records ESCALATED with reason RELEASE_REFUSED
-- and sends the holding reply (asof/gate.py). See docs/release-rules.md.

-- function: QUOTE_NORM
-- The verbatim-quote rule's normalisation (gate.normalise), in SQL: curly quotes and the en dash made plain,
-- whitespace runs collapsed, surrounding quote marks and trailing punctuation dropped, lower case. Python also
-- applies NFKC and unescapes HTML entities; Db2 12.1 LUW has no NORMALIZE_STRING (SQL0440N), and the shipped
-- clause texts are plain ASCII, so Db2 compares the remaining steps only.
CREATE OR REPLACE FUNCTION ASOF.QUOTE_NORM (P_TEXT VARCHAR(4000))
  RETURNS VARCHAR(4000)
  LANGUAGE SQL
  DETERMINISTIC
  NO EXTERNAL ACTION
  CONTAINS SQL
  RETURN LOWER(TRIM(REGEXP_REPLACE(REGEXP_REPLACE(TRIM(REGEXP_REPLACE(
           REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(P_TEXT, U&'\2018', ''''), U&'\2019', ''''),
                                   U&'\201C', '"'), U&'\201D', '"'), U&'\2013', '-'),
           '\s+', ' ')), '^[''"]+|[''"]+$', ''), '[.,;:!?' || U&'\2026' || ']+$', '')))
@

-- trigger: ANSWER_LEDGER_RELEASE_RULES
-- One pass over the claims: each released claim joined to the clause version in force on the customer's date.
-- WITH RS keeps the clause rows it read share-locked until the append commits, so a policy change cannot replace
-- a version between this check and the commit (APPLY_POLICY_CHANGE waits for it instead).
-- SECURED: ANSWER_LEDGER has column access control (05_masks.sql).
CREATE OR REPLACE TRIGGER ASOF.ANSWER_LEDGER_RELEASE_RULES
  NO CASCADE BEFORE INSERT ON ASOF.ANSWER_LEDGER
  REFERENCING NEW AS N
  FOR EACH ROW SECURED
  WHEN (N.DECISION IN ('PASS', 'CORRECTED'))
BEGIN
  DECLARE V_RELEASED SMALLINT;
  DECLARE V_ELEMENTS INTEGER;
  DECLARE V_CLAIMS INTEGER;
  DECLARE V_RELEASED_CLAIMS INTEGER;
  DECLARE V_OTHER_PASS INTEGER;
  DECLARE V_UNSUPPORTED INTEGER;
  DECLARE V_NOT_IN_FORCE INTEGER;
  DECLARE V_UNQUOTED INTEGER;

  IF JSON_EXISTS(N.VERDICTS_JSON, '$.claims[16]') THEN
    SIGNAL SQLSTATE '75003' SET MESSAGE_TEXT = 'A decision may carry at most 8 claims per check';
  END IF;
  SET V_RELEASED = CASE WHEN N.DECISION = 'CORRECTED' THEN 2 ELSE 1 END;
  -- Array entries, counted one literal index at a time, so an entry CLAIMS_FROM_JSON cannot read (no claim_no)
  -- is refused instead of skipped.
  SET V_ELEMENTS = (
                   CASE WHEN JSON_EXISTS(N.VERDICTS_JSON, '$.claims[0]') THEN 1 ELSE 0 END
                 + CASE WHEN JSON_EXISTS(N.VERDICTS_JSON, '$.claims[1]') THEN 1 ELSE 0 END
                 + CASE WHEN JSON_EXISTS(N.VERDICTS_JSON, '$.claims[2]') THEN 1 ELSE 0 END
                 + CASE WHEN JSON_EXISTS(N.VERDICTS_JSON, '$.claims[3]') THEN 1 ELSE 0 END
                 + CASE WHEN JSON_EXISTS(N.VERDICTS_JSON, '$.claims[4]') THEN 1 ELSE 0 END
                 + CASE WHEN JSON_EXISTS(N.VERDICTS_JSON, '$.claims[5]') THEN 1 ELSE 0 END
                 + CASE WHEN JSON_EXISTS(N.VERDICTS_JSON, '$.claims[6]') THEN 1 ELSE 0 END
                 + CASE WHEN JSON_EXISTS(N.VERDICTS_JSON, '$.claims[7]') THEN 1 ELSE 0 END
                 + CASE WHEN JSON_EXISTS(N.VERDICTS_JSON, '$.claims[8]') THEN 1 ELSE 0 END
                 + CASE WHEN JSON_EXISTS(N.VERDICTS_JSON, '$.claims[9]') THEN 1 ELSE 0 END
                 + CASE WHEN JSON_EXISTS(N.VERDICTS_JSON, '$.claims[10]') THEN 1 ELSE 0 END
                 + CASE WHEN JSON_EXISTS(N.VERDICTS_JSON, '$.claims[11]') THEN 1 ELSE 0 END
                 + CASE WHEN JSON_EXISTS(N.VERDICTS_JSON, '$.claims[12]') THEN 1 ELSE 0 END
                 + CASE WHEN JSON_EXISTS(N.VERDICTS_JSON, '$.claims[13]') THEN 1 ELSE 0 END
                 + CASE WHEN JSON_EXISTS(N.VERDICTS_JSON, '$.claims[14]') THEN 1 ELSE 0 END
                 + CASE WHEN JSON_EXISTS(N.VERDICTS_JSON, '$.claims[15]') THEN 1 ELSE 0 END);
  SELECT COUNT(*),
         COALESCE(SUM(CASE WHEN J.PASS_NO = V_RELEASED THEN 1 ELSE 0 END), 0),
         COALESCE(SUM(CASE WHEN J.PASS_NO IS NULL OR J.PASS_NO NOT IN (1, V_RELEASED) THEN 1 ELSE 0 END), 0),
         COALESCE(SUM(CASE WHEN J.PASS_NO = V_RELEASED
                            AND (J.VERDICT IS NULL OR J.VERDICT <> 'SUPPORTED' OR J.CLAUSE_ID IS NULL) THEN 1 ELSE 0 END), 0),
         COALESCE(SUM(CASE WHEN J.PASS_NO = V_RELEASED AND J.CLAUSE_ID IS NOT NULL AND P.CLAUSE_ID IS NULL
                           THEN 1 ELSE 0 END), 0),
         COALESCE(SUM(CASE WHEN J.PASS_NO = V_RELEASED AND P.CLAUSE_ID IS NOT NULL
                            AND (CHARACTER_LENGTH(ASOF.QUOTE_NORM(COALESCE(J.QUOTED_SPAN, '')), CODEUNITS32) < 12
                                 OR LOCATE(ASOF.QUOTE_NORM(J.QUOTED_SPAN), ASOF.QUOTE_NORM(P.CLAUSE_TEXT)) = 0)
                           THEN 1 ELSE 0 END), 0)
    INTO V_CLAIMS, V_RELEASED_CLAIMS, V_OTHER_PASS, V_UNSUPPORTED, V_NOT_IN_FORCE, V_UNQUOTED
    FROM TABLE(ASOF.CLAIMS_FROM_JSON(N.VERDICTS_JSON)) AS J
    LEFT JOIN ASOF.POLICY_CLAUSE FOR BUSINESS_TIME AS OF N.AS_OF_DATE AS P
      ON P.CLAUSE_ID = J.CLAUSE_ID AND P.DOC_ID = N.DOC_ID AND P.BUS_START = J.CLAUSE_BUS_START
     AND P.VERSION_LABEL = J.CLAUSE_VERSION
    WITH RS;

  IF V_CLAIMS <> V_ELEMENTS OR V_OTHER_PASS > 0 OR (N.DECISION = 'CORRECTED' AND V_RELEASED_CLAIMS = 0) THEN
    SIGNAL SQLSTATE '75083'
      SET MESSAGE_TEXT = 'Release refused: a PASS carries only the draft''s check, a CORRECTED answer the re-check of its rewrite';
  END IF;
  IF V_UNSUPPORTED > 0 THEN
    SIGNAL SQLSTATE '75080'
      SET MESSAGE_TEXT = 'Release refused: every claim given to the customer must be SUPPORTED by a cited clause';
  END IF;
  IF V_NOT_IN_FORCE > 0 THEN
    SIGNAL SQLSTATE '75081'
      SET MESSAGE_TEXT = 'Release refused: a claim cites a clause version that is not in force on the customer''s date';
  END IF;
  IF V_UNQUOTED > 0 THEN
    SIGNAL SQLSTATE '75082'
      SET MESSAGE_TEXT = 'Release refused: a claim''s quote is not in the text of the clause version it cites';
  END IF;
END
@

-- type: IMPACT_ROW
-- One row of CHANGE_IMPACT's result set, held in memory by PREVIEW_POLICY_CHANGE across its rollback.
CREATE TYPE ASOF.IMPACT_ROW AS ROW (
  KIND            VARCHAR(9),
  REF_ID          VARCHAR(32),
  FOR_FROM        DATE,
  FOR_TO          DATE,
  STATE           VARCHAR(12),
  CREATED_AT      TIMESTAMP(12),
  CITED_VERSION   VARCHAR(20),
  CURRENT_VERSION VARCHAR(1000),
  STATUS          VARCHAR(18),
  STALE_FROM      DATE)
@

-- type: IMPACT_ROWS
CREATE TYPE ASOF.IMPACT_ROWS AS ASOF.IMPACT_ROW ARRAY[]
@

-- procedure: PREVIEW_POLICY_CHANGE
-- What a policy change would do, computed by Db2 and then undone by Db2: under a savepoint it applies the change
-- through APPLY_POLICY_CHANGE (same arguments, same checks and SQLSTATEs), runs CHANGE_IMPACT on the changed policy
-- and copies its rows into an array, then ROLLBACK TO SAVEPOINT removes the new version, the split rows, the history
-- rows and the help-centre flags. It returns the counts APPLY_POLICY_CHANGE reported and, as its result set, exactly
-- the rows CHANGE_IMPACT returned. Nothing it did survives, whether or not the caller commits afterwards. On any
-- error it rolls back to the savepoint and re-raises the error unchanged (75010 to 75014 from APPLY_POLICY_CHANGE).
CREATE OR REPLACE PROCEDURE ASOF.PREVIEW_POLICY_CHANGE (
    IN  P_CLAUSE_ID     VARCHAR(32),
    IN  P_FROM          DATE,
    IN  P_TO            DATE,
    IN  P_VERSION_LABEL VARCHAR(20),
    IN  P_TEXT          VARCHAR(4000),
    IN  P_RULE_JSON     VARCHAR(2000),
    IN  P_EMBEDDING     VARCHAR(12000),
    IN  P_NOTE          VARCHAR(400),
    OUT P_ROWS          INTEGER,
    OUT P_FLAGGED       INTEGER)
  LANGUAGE SQL
  MODIFIES SQL DATA
  DYNAMIC RESULT SETS 1
BEGIN
  DECLARE V_ROW ASOF.IMPACT_ROW;
  DECLARE V_ROWS ASOF.IMPACT_ROWS;
  DECLARE V_N INTEGER DEFAULT 0;
  DECLARE V_DONE SMALLINT DEFAULT 0;
  DECLARE V_IMPACT RESULT_SET_LOCATOR VARYING;
  DECLARE C_OUT CURSOR WITH RETURN TO CALLER FOR
    SELECT T.KIND, T.REF_ID, T.FOR_FROM, T.FOR_TO, T.STATE, T.CREATED_AT, T.CITED_VERSION, T.CURRENT_VERSION,
           T.STATUS, T.STALE_FROM
    FROM UNNEST(V_ROWS) WITH ORDINALITY AS T (KIND, REF_ID, FOR_FROM, FOR_TO, STATE, CREATED_AT, CITED_VERSION,
                                              CURRENT_VERSION, STATUS, STALE_FROM, N)
    ORDER BY T.N;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET V_DONE = 1;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
      ROLLBACK TO SAVEPOINT ASOF_PREVIEW;
      RESIGNAL;
    END;

  SAVEPOINT ASOF_PREVIEW ON ROLLBACK RETAIN CURSORS;
  CALL ASOF.APPLY_POLICY_CHANGE(P_CLAUSE_ID, P_FROM, P_TO, P_VERSION_LABEL, P_TEXT, P_RULE_JSON, P_EMBEDDING, P_NOTE,
                                P_ROWS, P_FLAGGED);
  CALL ASOF.CHANGE_IMPACT(P_CLAUSE_ID);
  ASSOCIATE RESULT SET LOCATOR (V_IMPACT) WITH PROCEDURE ASOF.CHANGE_IMPACT;
  ALLOCATE C_IMPACT CURSOR FOR RESULT SET V_IMPACT;
  ROWS: LOOP
    FETCH C_IMPACT INTO V_ROW.KIND, V_ROW.REF_ID, V_ROW.FOR_FROM, V_ROW.FOR_TO, V_ROW.STATE, V_ROW.CREATED_AT,
                        V_ROW.CITED_VERSION, V_ROW.CURRENT_VERSION, V_ROW.STATUS, V_ROW.STALE_FROM;
    IF V_DONE = 1 THEN
      LEAVE ROWS;
    END IF;
    SET V_N = V_N + 1;
    SET V_ROWS[V_N] = V_ROW;
  END LOOP;
  CLOSE C_IMPACT;
  ROLLBACK TO SAVEPOINT ASOF_PREVIEW;
  RELEASE SAVEPOINT ASOF_PREVIEW;
  OPEN C_OUT;
END
@
