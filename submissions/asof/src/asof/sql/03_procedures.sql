-- Ledger routines. All are LANGUAGE SQL, so they run inside the Db2 engine (no fenced
-- process) and execute with the owner's privileges: the app user can CALL them without
-- holding INSERT on any table.

-- function: SHA256_HEX
CREATE OR REPLACE FUNCTION ASOF.SHA256_HEX (P_TEXT VARCHAR(30000))
  RETURNS CHAR(64)
  LANGUAGE SQL
  DETERMINISTIC
  NO EXTERNAL ACTION
  CONTAINS SQL
  RETURN LOWER(HEX(HASH(P_TEXT, 2)))
@

-- function: LEDGER_ROW_HASH
-- SHA-256 over the previous row's hash followed by the SHA-256 of every field. Fixed-length
-- digests make field boundaries unambiguous and keep the input far below Db2's 32 KB limit.
CREATE OR REPLACE FUNCTION ASOF.LEDGER_ROW_HASH (
    P_PREV_HASH CHAR(64), P_LEDGER_ID BIGINT, P_REQUEST_ID CHAR(36), P_CREATED_AT TIMESTAMP(12),
    P_CHANNEL VARCHAR(20), P_DOC_ID VARCHAR(32), P_AS_OF DATE, P_QUESTION VARCHAR(2000),
    P_DRAFT VARCHAR(4000), P_FINAL VARCHAR(4000), P_DECISION VARCHAR(12), P_REASON VARCHAR(40),
    P_MODEL VARCHAR(200), P_PROMPT_VERSION VARCHAR(40), P_LATENCY_MS INTEGER, P_VERDICTS VARCHAR(30000))
  RETURNS CHAR(64)
  LANGUAGE SQL
  DETERMINISTIC
  NO EXTERNAL ACTION
  CONTAINS SQL
  RETURN ASOF.SHA256_HEX(
       P_PREV_HASH
    || ASOF.SHA256_HEX(RTRIM(CHAR(P_LEDGER_ID)))
    || ASOF.SHA256_HEX(P_REQUEST_ID)
    || ASOF.SHA256_HEX(CHAR(P_CREATED_AT))
    || ASOF.SHA256_HEX(P_CHANNEL)
    || ASOF.SHA256_HEX(P_DOC_ID)
    || ASOF.SHA256_HEX(CHAR(P_AS_OF, ISO))
    || ASOF.SHA256_HEX(P_QUESTION)
    || ASOF.SHA256_HEX(P_DRAFT)
    || ASOF.SHA256_HEX(P_FINAL)
    || ASOF.SHA256_HEX(P_DECISION)
    || ASOF.SHA256_HEX(P_REASON)
    || ASOF.SHA256_HEX(P_MODEL)
    || ASOF.SHA256_HEX(P_PROMPT_VERSION)
    || ASOF.SHA256_HEX(RTRIM(CHAR(P_LATENCY_MS)))
    || ASOF.SHA256_HEX(P_VERDICTS))
@

-- function: CLAIMS_FROM_JSON
-- One row per entry of $.claims in a verdicts document (at most 16: 8 claims in the draft
-- check plus 8 in the re-check of a rewrite). Db2's JSON_TABLE takes only 'strict $' as its
-- row path (no NESTED PATH at this level), so each array position is read with a literal
-- index and the branches are unioned.
CREATE OR REPLACE FUNCTION ASOF.CLAIMS_FROM_JSON (P_VERDICTS VARCHAR(30000))
  RETURNS TABLE (PASS_NO SMALLINT, CLAIM_NO SMALLINT, CLAIM_TEXT VARCHAR(1000), AREA VARCHAR(40), VERDICT VARCHAR(14), LLM_VERDICT VARCHAR(14), RULE_CHECK VARCHAR(16), CLAUSE_ID VARCHAR(32), CLAUSE_VERSION VARCHAR(20), CLAUSE_BUS_START DATE, CLAUSE_SYS_START TIMESTAMP(12), DISTANCE DOUBLE, QUOTED_SPAN VARCHAR(1000))
  LANGUAGE SQL
  DETERMINISTIC
  NO EXTERNAL ACTION
  READS SQL DATA
  RETURN
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[0].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[0].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[0].text',
                   AREA             VARCHAR(40)   PATH '$.claims[0].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[0].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[0].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[0].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[0].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[0].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[0].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[0].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[0].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[0].quoted_span')
           ERROR ON ERROR) AS J0
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[1].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[1].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[1].text',
                   AREA             VARCHAR(40)   PATH '$.claims[1].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[1].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[1].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[1].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[1].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[1].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[1].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[1].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[1].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[1].quoted_span')
           ERROR ON ERROR) AS J1
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[2].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[2].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[2].text',
                   AREA             VARCHAR(40)   PATH '$.claims[2].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[2].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[2].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[2].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[2].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[2].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[2].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[2].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[2].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[2].quoted_span')
           ERROR ON ERROR) AS J2
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[3].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[3].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[3].text',
                   AREA             VARCHAR(40)   PATH '$.claims[3].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[3].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[3].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[3].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[3].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[3].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[3].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[3].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[3].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[3].quoted_span')
           ERROR ON ERROR) AS J3
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[4].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[4].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[4].text',
                   AREA             VARCHAR(40)   PATH '$.claims[4].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[4].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[4].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[4].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[4].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[4].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[4].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[4].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[4].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[4].quoted_span')
           ERROR ON ERROR) AS J4
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[5].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[5].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[5].text',
                   AREA             VARCHAR(40)   PATH '$.claims[5].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[5].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[5].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[5].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[5].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[5].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[5].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[5].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[5].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[5].quoted_span')
           ERROR ON ERROR) AS J5
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[6].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[6].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[6].text',
                   AREA             VARCHAR(40)   PATH '$.claims[6].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[6].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[6].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[6].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[6].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[6].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[6].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[6].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[6].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[6].quoted_span')
           ERROR ON ERROR) AS J6
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[7].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[7].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[7].text',
                   AREA             VARCHAR(40)   PATH '$.claims[7].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[7].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[7].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[7].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[7].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[7].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[7].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[7].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[7].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[7].quoted_span')
           ERROR ON ERROR) AS J7
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[8].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[8].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[8].text',
                   AREA             VARCHAR(40)   PATH '$.claims[8].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[8].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[8].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[8].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[8].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[8].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[8].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[8].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[8].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[8].quoted_span')
           ERROR ON ERROR) AS J8
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[9].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[9].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[9].text',
                   AREA             VARCHAR(40)   PATH '$.claims[9].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[9].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[9].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[9].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[9].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[9].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[9].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[9].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[9].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[9].quoted_span')
           ERROR ON ERROR) AS J9
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[10].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[10].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[10].text',
                   AREA             VARCHAR(40)   PATH '$.claims[10].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[10].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[10].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[10].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[10].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[10].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[10].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[10].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[10].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[10].quoted_span')
           ERROR ON ERROR) AS J10
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[11].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[11].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[11].text',
                   AREA             VARCHAR(40)   PATH '$.claims[11].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[11].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[11].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[11].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[11].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[11].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[11].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[11].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[11].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[11].quoted_span')
           ERROR ON ERROR) AS J11
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[12].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[12].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[12].text',
                   AREA             VARCHAR(40)   PATH '$.claims[12].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[12].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[12].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[12].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[12].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[12].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[12].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[12].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[12].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[12].quoted_span')
           ERROR ON ERROR) AS J12
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[13].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[13].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[13].text',
                   AREA             VARCHAR(40)   PATH '$.claims[13].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[13].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[13].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[13].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[13].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[13].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[13].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[13].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[13].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[13].quoted_span')
           ERROR ON ERROR) AS J13
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[14].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[14].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[14].text',
                   AREA             VARCHAR(40)   PATH '$.claims[14].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[14].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[14].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[14].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[14].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[14].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[14].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[14].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[14].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[14].quoted_span')
           ERROR ON ERROR) AS J14
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[15].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[15].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[15].text',
                   AREA             VARCHAR(40)   PATH '$.claims[15].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[15].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[15].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[15].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[15].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[15].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[15].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[15].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[15].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[15].quoted_span')
           ERROR ON ERROR) AS J15
    WHERE CLAIM_NO IS NOT NULL
@

-- procedure: APPEND_LEDGER
-- Appends one decision and its claim citations atomically. Locks CHAIN_HEAD first, so
-- concurrent callers queue instead of forking the chain, and assigns the next LEDGER_ID.
-- The caller commits.
CREATE OR REPLACE PROCEDURE ASOF.APPEND_LEDGER (
    IN  P_REQUEST_ID     CHAR(36),
    IN  P_CHANNEL        VARCHAR(20),
    IN  P_DOC_ID         VARCHAR(32),
    IN  P_AS_OF          DATE,
    IN  P_QUESTION       VARCHAR(2000),
    IN  P_DRAFT          VARCHAR(4000),
    IN  P_FINAL          VARCHAR(4000),
    IN  P_DECISION       VARCHAR(12),
    IN  P_REASON         VARCHAR(40),
    IN  P_MODEL          VARCHAR(200),
    IN  P_PROMPT_VERSION VARCHAR(40),
    IN  P_LATENCY_MS     INTEGER,
    IN  P_VERDICTS       VARCHAR(30000),
    OUT P_LEDGER_ID      BIGINT,
    OUT P_ROW_HASH       CHAR(64),
    OUT P_CREATED_AT     TIMESTAMP(12))
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  DECLARE V_LAST BIGINT;
  DECLARE V_PREV CHAR(64);

  UPDATE ASOF.CHAIN_HEAD SET LAST_LEDGER_ID = LAST_LEDGER_ID WHERE HEAD_ID = 1;
  SET (V_LAST, V_PREV) = (SELECT LAST_LEDGER_ID, LAST_HASH FROM ASOF.CHAIN_HEAD WHERE HEAD_ID = 1);
  IF V_PREV IS NULL THEN
    SIGNAL SQLSTATE '75002' SET MESSAGE_TEXT = 'CHAIN_HEAD is missing: run setup';
  END IF;
  IF JSON_EXISTS(P_VERDICTS, '$.claims[16]') THEN
    SIGNAL SQLSTATE '75003' SET MESSAGE_TEXT = 'A decision may carry at most 8 claims per check';
  END IF;

  SET P_LEDGER_ID = V_LAST + 1;
  SET P_CREATED_AT = CURRENT TIMESTAMP(12);
  SET P_ROW_HASH = ASOF.LEDGER_ROW_HASH(V_PREV, P_LEDGER_ID, P_REQUEST_ID, P_CREATED_AT, P_CHANNEL,
                                        P_DOC_ID, P_AS_OF, P_QUESTION, P_DRAFT, P_FINAL, P_DECISION,
                                        P_REASON, P_MODEL, P_PROMPT_VERSION, P_LATENCY_MS, P_VERDICTS);

  INSERT INTO ASOF.ANSWER_LEDGER (LEDGER_ID, REQUEST_ID, CREATED_AT, CHANNEL, DOC_ID, AS_OF_DATE,
      QUESTION_REDACTED, DRAFT_REDACTED, FINAL_ANSWER, DECISION, REASON_CODE, MODEL_INFO,
      PROMPT_VERSION, LATENCY_MS, VERDICTS_JSON, PREV_HASH, ROW_HASH)
    VALUES (P_LEDGER_ID, P_REQUEST_ID, P_CREATED_AT, P_CHANNEL, P_DOC_ID, P_AS_OF,
      P_QUESTION, P_DRAFT, P_FINAL, P_DECISION, P_REASON, P_MODEL,
      P_PROMPT_VERSION, P_LATENCY_MS, P_VERDICTS, V_PREV, P_ROW_HASH);

  INSERT INTO ASOF.CLAIM_CITATION (LEDGER_ID, PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT,
      RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN)
    SELECT P_LEDGER_ID, j.PASS_NO, j.CLAIM_NO, j.CLAIM_TEXT, j.AREA, j.VERDICT, j.LLM_VERDICT,
           j.RULE_CHECK, j.CLAUSE_ID, j.CLAUSE_VERSION, j.CLAUSE_BUS_START, j.CLAUSE_SYS_START,
           j.DISTANCE, j.QUOTED_SPAN
    FROM TABLE(ASOF.CLAIMS_FROM_JSON(P_VERDICTS)) AS j;

  UPDATE ASOF.CHAIN_HEAD SET LAST_LEDGER_ID = P_LEDGER_ID, LAST_HASH = P_ROW_HASH WHERE HEAD_ID = 1;
END
@

-- procedure: VERIFY_CHAIN
-- Recomputes every row hash in order and checks: consecutive IDs, each PREV_HASH equal to
-- the previous ROW_HASH, each ROW_HASH equal to the hash of the row's content, the chain
-- head pointing at the last row, and the citation rows matching the hashed verdicts.
CREATE OR REPLACE PROCEDURE ASOF.VERIFY_CHAIN (
    OUT P_STATUS    VARCHAR(12),
    OUT P_CHECKED   BIGINT,
    OUT P_FIRST_BAD BIGINT,
    OUT P_DETAIL    VARCHAR(300))
  LANGUAGE SQL
  READS SQL DATA
BEGIN
  DECLARE V_PREV CHAR(64);
  DECLARE V_EXPECT BIGINT DEFAULT 1;
  DECLARE V_HEAD_ID BIGINT;
  DECLARE V_HEAD_HASH CHAR(64);

  SET V_PREV = REPEAT('0', 64);
  SET P_STATUS = 'OK';
  SET P_CHECKED = 0;
  SET P_FIRST_BAD = NULL;
  SET P_DETAIL = NULL;

  ROWS: FOR R AS SELECT LEDGER_ID, REQUEST_ID, CREATED_AT, CHANNEL, DOC_ID, AS_OF_DATE, QUESTION_REDACTED,
                        DRAFT_REDACTED, FINAL_ANSWER, DECISION, REASON_CODE, MODEL_INFO, PROMPT_VERSION,
                        LATENCY_MS, VERDICTS_JSON, PREV_HASH, ROW_HASH
                 FROM ASOF.ANSWER_LEDGER ORDER BY LEDGER_ID
  DO
    IF R.LEDGER_ID <> V_EXPECT THEN
      SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', V_EXPECT, 'ledger row is missing: IDs are not consecutive');
      LEAVE ROWS;
    END IF;
    IF R.PREV_HASH <> V_PREV THEN
      SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', R.LEDGER_ID, 'PREV_HASH does not match the previous row');
      LEAVE ROWS;
    END IF;
    IF ASOF.LEDGER_ROW_HASH(R.PREV_HASH, R.LEDGER_ID, R.REQUEST_ID, R.CREATED_AT, R.CHANNEL, R.DOC_ID,
                            R.AS_OF_DATE, R.QUESTION_REDACTED, R.DRAFT_REDACTED, R.FINAL_ANSWER,
                            R.DECISION, R.REASON_CODE, R.MODEL_INFO, R.PROMPT_VERSION, R.LATENCY_MS,
                            R.VERDICTS_JSON) <> R.ROW_HASH THEN
      SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', R.LEDGER_ID, 'row content does not match its ROW_HASH');
      LEAVE ROWS;
    END IF;
    SET V_PREV = R.ROW_HASH;
    SET V_EXPECT = V_EXPECT + 1;
    SET P_CHECKED = P_CHECKED + 1;
  END FOR;

  IF P_STATUS = 'OK' THEN
    SET (V_HEAD_ID, V_HEAD_HASH) = (SELECT LAST_LEDGER_ID, LAST_HASH FROM ASOF.CHAIN_HEAD WHERE HEAD_ID = 1);
    IF V_HEAD_ID IS NULL OR V_HEAD_ID <> P_CHECKED OR V_HEAD_HASH <> V_PREV THEN
      SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', P_CHECKED + 1, 'chain head does not point at the last ledger row');
    END IF;
  END IF;

  IF P_STATUS = 'OK' THEN
    SET P_FIRST_BAD = (
      SELECT MIN(L.LEDGER_ID)
      FROM ASOF.ANSWER_LEDGER L
      WHERE (SELECT COUNT(*) FROM ASOF.CLAIM_CITATION C WHERE C.LEDGER_ID = L.LEDGER_ID)
            <> (SELECT COUNT(*) FROM TABLE(ASOF.CLAIMS_FROM_JSON(L.VERDICTS_JSON)) AS J)
         OR EXISTS (
            SELECT 1 FROM ASOF.CLAIM_CITATION C
            WHERE C.LEDGER_ID = L.LEDGER_ID
              AND NOT EXISTS (
                SELECT 1 FROM TABLE(ASOF.CLAIMS_FROM_JSON(L.VERDICTS_JSON)) AS J
                WHERE J.PASS_NO = C.PASS_NO AND J.CLAIM_NO = C.CLAIM_NO AND J.VERDICT = C.VERDICT
                  AND COALESCE(J.CLAUSE_ID, '') = COALESCE(C.CLAUSE_ID, '')
                  AND COALESCE(J.CLAUSE_BUS_START, DATE('0001-01-01')) = COALESCE(C.CLAUSE_BUS_START, DATE('0001-01-01')))));
    IF P_FIRST_BAD IS NOT NULL THEN
      SET (P_STATUS, P_DETAIL) = ('BROKEN', 'claim citations do not match the hashed verdicts');
    END IF;
  END IF;

  -- The ibm_db CLI driver cannot return NULL OUT values (CLI0110E), so report 0 and a message.
  SET P_FIRST_BAD = COALESCE(P_FIRST_BAD, 0);
  SET P_DETAIL = COALESCE(P_DETAIL, 'every row, link and citation verified');
END
@

-- procedure: APPLY_POLICY_CHANGE
-- A new clause version for a business-time period. FOR PORTION OF BUSINESS_TIME makes Db2
-- split the affected rows; system versioning keeps every replaced row in the history
-- table, so replay still shows what applied before. Help-centre answers whose period the
-- change touches are flagged NEEDS_REVIEW. Granted to the policy editor only.
CREATE OR REPLACE PROCEDURE ASOF.APPLY_POLICY_CHANGE (
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
BEGIN
  IF P_FROM IS NULL OR P_TO IS NULL OR P_TO <= P_FROM THEN
    SIGNAL SQLSTATE '75010' SET MESSAGE_TEXT = 'The change must end after it starts';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM ASOF.POLICY_CLAUSE WHERE CLAUSE_ID = P_CLAUSE_ID) THEN
    SIGNAL SQLSTATE '75011' SET MESSAGE_TEXT = 'Unknown clause';
  END IF;
  IF EXISTS (SELECT 1 FROM ASOF.POLICY_CLAUSE WHERE CLAUSE_ID = P_CLAUSE_ID AND VERSION_LABEL = P_VERSION_LABEL) THEN
    SIGNAL SQLSTATE '75012' SET MESSAGE_TEXT = 'That version label is already in use for this clause';
  END IF;

  UPDATE ASOF.POLICY_CLAUSE
    FOR PORTION OF BUSINESS_TIME FROM P_FROM TO P_TO
    SET VERSION_LABEL = P_VERSION_LABEL,
        CLAUSE_TEXT   = P_TEXT,
        RULE_JSON     = P_RULE_JSON,
        EMBEDDING     = VECTOR(P_EMBEDDING, 384, FLOAT32),
        CHANGE_NOTE   = P_NOTE,
        CHANGED_BY    = SESSION_USER
    WHERE CLAUSE_ID = P_CLAUSE_ID;
  GET DIAGNOSTICS P_ROWS = ROW_COUNT;
  IF P_ROWS = 0 THEN
    SIGNAL SQLSTATE '75013' SET MESSAGE_TEXT = 'No existing version of this clause overlaps that period';
  END IF;

  UPDATE ASOF.PUBLISHED_ANSWER
    SET STATUS = 'NEEDS_REVIEW'
    WHERE CITED_CLAUSE_ID = P_CLAUSE_ID AND STATUS = 'LIVE'
      AND APPLIES_FROM < P_TO AND APPLIES_TO > P_FROM;
  GET DIAGNOSTICS P_FLAGGED = ROW_COUNT;
END
@

-- procedure: CHANGE_IMPACT
-- Everything that relied on a clause, judged against the policy as it stands now.
--   ANSWER rows: released decisions (PASS, or the re-checked rewrite of a CORRECTED one)
--     that cited the clause. HISTORICALLY_VALID if the version in force for the customer's
--     date is still the one cited; STALE if that date now falls under a different version.
--   PUBLISHED rows: help-centre answers citing the clause. NEEDS_REVIEW if any other version
--     now applies within the dates they cover, from STALE_FROM; otherwise STILL_VALID.
CREATE OR REPLACE PROCEDURE ASOF.CHANGE_IMPACT (IN P_CLAUSE_ID VARCHAR(32))
  LANGUAGE SQL
  READS SQL DATA
  DYNAMIC RESULT SETS 1
BEGIN
  DECLARE C1 CURSOR WITH RETURN TO CALLER FOR
    WITH RELEASED AS (
      SELECT DISTINCT L.LEDGER_ID, L.AS_OF_DATE, L.DECISION, L.CREATED_AT, C.CLAUSE_VERSION, C.CLAUSE_BUS_START
      FROM ASOF.ANSWER_LEDGER L
      JOIN ASOF.CLAIM_CITATION C ON C.LEDGER_ID = L.LEDGER_ID
      WHERE C.CLAUSE_ID = P_CLAUSE_ID AND C.VERDICT = 'SUPPORTED'
        AND ((L.DECISION = 'PASS' AND C.PASS_NO = 1) OR (L.DECISION = 'CORRECTED' AND C.PASS_NO = 2))
    )
    SELECT 'ANSWER' AS KIND, RTRIM(CHAR(R.LEDGER_ID)) AS REF_ID, R.AS_OF_DATE AS FOR_FROM,
           CAST(NULL AS DATE) AS FOR_TO, R.DECISION AS STATE, R.CREATED_AT,
           R.CLAUSE_VERSION AS CITED_VERSION, COALESCE(P.VERSION_LABEL, '(none)') AS CURRENT_VERSION,
           CASE WHEN P.VERSION_LABEL = R.CLAUSE_VERSION THEN 'HISTORICALLY_VALID' ELSE 'STALE' END AS STATUS,
           CASE WHEN P.VERSION_LABEL = R.CLAUSE_VERSION THEN CAST(NULL AS DATE) ELSE R.AS_OF_DATE END AS STALE_FROM
    FROM RELEASED R
    LEFT JOIN ASOF.POLICY_CLAUSE P
      ON P.CLAUSE_ID = P_CLAUSE_ID AND P.BUS_START <= R.AS_OF_DATE AND P.BUS_END > R.AS_OF_DATE
    UNION ALL
    SELECT 'PUBLISHED', A.ANSWER_ID, A.APPLIES_FROM, A.APPLIES_TO, A.STATUS, CAST(NULL AS TIMESTAMP(12)),
           A.CITED_VERSION,
           COALESCE((SELECT LISTAGG(DISTINCT P.VERSION_LABEL, ', ') WITHIN GROUP (ORDER BY P.VERSION_LABEL)
                     FROM ASOF.POLICY_CLAUSE P
                     WHERE P.CLAUSE_ID = P_CLAUSE_ID AND P.BUS_START < A.APPLIES_TO AND P.BUS_END > A.APPLIES_FROM), '(none)'),
           CASE WHEN EXISTS (SELECT 1 FROM ASOF.POLICY_CLAUSE P
                             WHERE P.CLAUSE_ID = P_CLAUSE_ID AND P.BUS_START < A.APPLIES_TO AND P.BUS_END > A.APPLIES_FROM
                               AND P.VERSION_LABEL <> A.CITED_VERSION)
                THEN 'NEEDS_REVIEW' ELSE 'STILL_VALID' END,
           (SELECT MIN(GREATEST(P.BUS_START, A.APPLIES_FROM)) FROM ASOF.POLICY_CLAUSE P
             WHERE P.CLAUSE_ID = P_CLAUSE_ID AND P.BUS_START < A.APPLIES_TO AND P.BUS_END > A.APPLIES_FROM
               AND P.VERSION_LABEL <> A.CITED_VERSION)
    FROM ASOF.PUBLISHED_ANSWER A
    WHERE A.CITED_CLAUSE_ID = P_CLAUSE_ID
    ORDER BY 1, 3, 2;
  OPEN C1;
END
@
