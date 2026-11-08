-- Ledger routines. All are LANGUAGE SQL, so they run inside the Db2 engine (no fenced
-- process) and execute with the owner's privileges: the app user can CALL them without
-- holding INSERT on any table.
-- No routine passes a masked ledger column (05_masks.sql) straight to a function: Db2 rejects
-- that for functions that are not SECURED (SQL20473N). VERIFY_CHAIN fetches each row into
-- variables first and hashes those.

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

-- procedure: APPEND_LEDGER_ROW
-- Appends one decision and its claim citations atomically. Locks CHAIN_HEAD first, so
-- concurrent callers queue instead of forking the chain, and assigns the next LEDGER_ID.
-- Granted to nobody: the runtime user reaches it only through APPEND_LEDGER (the check's own
-- decisions) and RESOLVE_ESCALATION (a specialist's reply). The caller commits.
CREATE OR REPLACE PROCEDURE ASOF.APPEND_LEDGER_ROW (
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

-- procedure: APPEND_LEDGER
-- The way the check records its decisions. A REVIEWED row (a specialist's reply) is refused here: it is
-- only ever written by RESOLVE_ESCALATION, which enforces the inbox's rules first.
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
  IF P_DECISION IS NULL OR P_DECISION NOT IN ('PASS', 'CORRECTED', 'ESCALATED') THEN
    SIGNAL SQLSTATE '75004' SET MESSAGE_TEXT = 'APPEND_LEDGER records the check''s decisions; a specialist''s reply goes through RESOLVE_ESCALATION';
  END IF;
  CALL ASOF.APPEND_LEDGER_ROW(P_REQUEST_ID, P_CHANNEL, P_DOC_ID, P_AS_OF, P_QUESTION, P_DRAFT, P_FINAL, P_DECISION,
                              P_REASON, P_MODEL, P_PROMPT_VERSION, P_LATENCY_MS, P_VERDICTS,
                              P_LEDGER_ID, P_ROW_HASH, P_CREATED_AT);
END
@

-- procedure: VERIFY_CHAIN
-- Recomputes every row hash in order and checks: consecutive IDs, each PREV_HASH equal to
-- the previous ROW_HASH, each ROW_HASH equal to the hash of the row's content, the chain
-- head pointing at the last row, and the citation rows matching the hashed verdicts.
-- Rows are fetched into variables before hashing: the free-text columns carry column masks,
-- and Db2 accepts a masked column only as the argument of a SECURED function. Run as the
-- runtime user (role ASOF_TEXT_READER), the fetch returns the real values. Anyone else would
-- hash '[masked]' and report a chain that is not broken as broken, so the procedure refuses
-- them up front (75030) instead.
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
  DECLARE C_ROWS CURSOR FOR
    SELECT LEDGER_ID, REQUEST_ID, CREATED_AT, CHANNEL, DOC_ID, AS_OF_DATE, QUESTION_REDACTED,
           DRAFT_REDACTED, FINAL_ANSWER, DECISION, REASON_CODE, MODEL_INFO, PROMPT_VERSION,
           LATENCY_MS, VERDICTS_JSON, PREV_HASH, ROW_HASH
    FROM ASOF.ANSWER_LEDGER ORDER BY LEDGER_ID;
  DECLARE C_VERDICTS CURSOR FOR
    SELECT LEDGER_ID, VERDICTS_JSON FROM ASOF.ANSWER_LEDGER ORDER BY LEDGER_ID;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET V_DONE = 1;

  IF VERIFY_ROLE_FOR_USER(SESSION_USER, 'ASOF_TEXT_READER') <> 1 THEN
    SIGNAL SQLSTATE '75030' SET MESSAGE_TEXT = 'VERIFY_CHAIN needs role ASOF_TEXT_READER: ledger text is masked for this user';
  END IF;
  SET V_PREV = REPEAT('0', 64);
  SET P_STATUS = 'OK';
  SET P_CHECKED = 0;
  SET P_FIRST_BAD = NULL;
  SET P_DETAIL = NULL;

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

  IF P_STATUS = 'OK' THEN
    SET (V_HEAD_ID, V_HEAD_HASH) = (SELECT LAST_LEDGER_ID, LAST_HASH FROM ASOF.CHAIN_HEAD WHERE HEAD_ID = 1);
    IF V_HEAD_ID IS NULL OR V_HEAD_ID <> P_CHECKED OR V_HEAD_HASH <> V_PREV THEN
      SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', P_CHECKED + 1, 'chain head does not point at the last ledger row');
    END IF;
  END IF;

  IF P_STATUS = 'OK' THEN
    SET V_DONE = 0;
    OPEN C_VERDICTS;
    CITES: LOOP
      FETCH C_VERDICTS INTO V_ID, V_VERDICTS;
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
    CLOSE C_VERDICTS;
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
  -- P_EMBEDDING NULL means: Db2 embeds the new text itself with the in-database model
  -- (TO_EMBEDDING ... USING EMBEDDER, registered by setup). Dynamic SQL, so the procedure
  -- compiles whether or not a model is configured.
  DECLARE V_VEC   VECTOR(384, FLOAT32);
  DECLARE V_TITLE VARCHAR(200);
  DECLARE S_EMBED STATEMENT;
  DECLARE C_EMBED CURSOR FOR S_EMBED;
  IF P_FROM IS NULL OR P_TO IS NULL OR P_TO <= P_FROM THEN
    SIGNAL SQLSTATE '75010' SET MESSAGE_TEXT = 'The change must end after it starts';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM ASOF.POLICY_CLAUSE WHERE CLAUSE_ID = P_CLAUSE_ID) THEN
    SIGNAL SQLSTATE '75011' SET MESSAGE_TEXT = 'Unknown clause';
  END IF;
  IF EXISTS (SELECT 1 FROM ASOF.POLICY_CLAUSE WHERE CLAUSE_ID = P_CLAUSE_ID AND VERSION_LABEL = P_VERSION_LABEL) THEN
    SIGNAL SQLSTATE '75012' SET MESSAGE_TEXT = 'That version label is already in use for this clause';
  END IF;

  IF P_EMBEDDING IS NULL THEN
    BEGIN
      DECLARE EXIT HANDLER FOR SQLEXCEPTION
        SIGNAL SQLSTATE '75014' SET MESSAGE_TEXT = 'In-database embedding failed: no EMBEDDER model, or the endpoint refused';
      SET V_TITLE = (SELECT TITLE FROM ASOF.POLICY_CLAUSE WHERE CLAUSE_ID = P_CLAUSE_ID FETCH FIRST 1 ROW ONLY);
      -- Same text the seed embeds: title, a full stop, the clause (embeddings.clause_embedding_text).
      PREPARE S_EMBED FROM 'VALUES TO_EMBEDDING(CAST(? AS VARCHAR(4300)) USING ASOF.EMBEDDER)';
      OPEN C_EMBED USING V_TITLE || '. ' || P_TEXT;
      FETCH C_EMBED INTO V_VEC;
      CLOSE C_EMBED;
    END;
  ELSE
    SET V_VEC = VECTOR(P_EMBEDDING, 384, FLOAT32);
  END IF;

  UPDATE ASOF.POLICY_CLAUSE
    FOR PORTION OF BUSINESS_TIME FROM P_FROM TO P_TO
    SET VERSION_LABEL = P_VERSION_LABEL,
        CLAUSE_TEXT   = P_TEXT,
        RULE_JSON     = P_RULE_JSON,
        EMBEDDING     = V_VEC,
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
--   ANSWER rows: released decisions (PASS, the re-checked rewrite of a CORRECTED one, or a
--     specialist's checked reply, REVIEWED) that cited the clause. HISTORICALLY_VALID if the version in force for the customer's
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
        AND ((L.DECISION IN ('PASS', 'REVIEWED') AND C.PASS_NO = 1)
             OR (L.DECISION = 'CORRECTED' AND C.PASS_NO = 2))
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

-- procedure: ADD_SUGGESTION
-- The change-impact agent stores a drafted correction (runtime user, EXECUTE only).
CREATE OR REPLACE PROCEDURE ASOF.ADD_SUGGESTION (
    IN  P_ANSWER_ID      VARCHAR(32),
    IN  P_CLAUSE_ID      VARCHAR(32),
    IN  P_STALE_FROM     DATE,
    IN  P_VERSION        VARCHAR(20),
    IN  P_TEXT           VARCHAR(4000),
    IN  P_DECISION       VARCHAR(12),
    IN  P_LEDGER_ID      BIGINT,        -- 0 when the check left no ledger row
    IN  P_TRACE          VARCHAR(8000),
    OUT P_SUGGESTION_ID  BIGINT)
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  IF NOT EXISTS (SELECT 1 FROM ASOF.PUBLISHED_ANSWER WHERE ANSWER_ID = P_ANSWER_ID AND CITED_CLAUSE_ID = P_CLAUSE_ID) THEN
    SIGNAL SQLSTATE '75020' SET MESSAGE_TEXT = 'That help-centre answer does not cite this clause';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM ASOF.POLICY_CLAUSE FOR BUSINESS_TIME AS OF P_STALE_FROM
                 WHERE CLAUSE_ID = P_CLAUSE_ID AND VERSION_LABEL = P_VERSION) THEN
    SIGNAL SQLSTATE '75021' SET MESSAGE_TEXT = 'That clause version is not the one in force from that date';
  END IF;
  INSERT INTO ASOF.ANSWER_SUGGESTION (ANSWER_ID, CLAUSE_ID, STALE_FROM, BASED_ON_VERSION, SUGGESTED_TEXT,
                                      CHECK_DECISION, CHECK_LEDGER_ID, AGENT_TRACE)
    VALUES (P_ANSWER_ID, P_CLAUSE_ID, P_STALE_FROM, P_VERSION, P_TEXT, P_DECISION, NULLIF(P_LEDGER_ID, 0), P_TRACE);
  SET P_SUGGESTION_ID = IDENTITY_VAL_LOCAL();
END
@

-- procedure: DECIDE_SUGGESTION
-- The policy editor approves or rejects a suggestion. Approval publishes it without rewriting
-- history: the old answer keeps the dates before STALE_FROM (it was right for them), and the
-- corrected answer covers STALE_FROM to the old end date, citing the version in force then.
CREATE OR REPLACE PROCEDURE ASOF.DECIDE_SUGGESTION (
    IN  P_SUGGESTION_ID  BIGINT,
    IN  P_APPROVE        SMALLINT,
    OUT P_PUBLISHED_ID   VARCHAR(32))
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  DECLARE V_ANSWER VARCHAR(32);
  DECLARE V_CLAUSE VARCHAR(32);
  DECLARE V_FROM DATE;
  DECLARE V_VERSION VARCHAR(20);
  DECLARE V_TEXT VARCHAR(4000);
  DECLARE V_DECISION VARCHAR(12);
  DECLARE V_STATUS VARCHAR(12);
  DECLARE V_BUS_START DATE;
  DECLARE V_OLD_FROM DATE;
  DECLARE V_OLD_TO DATE;
  DECLARE V_NEW_ID VARCHAR(32);
  DECLARE V_CLAIMED INTEGER;

  SET P_PUBLISHED_ID = '';
  SELECT ANSWER_ID, CLAUSE_ID, STALE_FROM, BASED_ON_VERSION, SUGGESTED_TEXT, CHECK_DECISION, STATUS
    INTO V_ANSWER, V_CLAUSE, V_FROM, V_VERSION, V_TEXT, V_DECISION, V_STATUS
    FROM ASOF.ANSWER_SUGGESTION WHERE SUGGESTION_ID = P_SUGGESTION_ID;
  IF V_STATUS IS NULL THEN
    SIGNAL SQLSTATE '75022' SET MESSAGE_TEXT = 'Unknown suggestion';
  END IF;
  IF P_APPROVE <> 0 AND V_DECISION NOT IN ('PASS', 'CORRECTED') THEN
    SIGNAL SQLSTATE '75024' SET MESSAGE_TEXT = 'Only a draft the check released can be approved';
  END IF;

  -- Claim the suggestion atomically: of two editors deciding at once, exactly one gets it.
  UPDATE ASOF.ANSWER_SUGGESTION
    SET STATUS = CASE WHEN P_APPROVE <> 0 THEN 'APPROVED' ELSE 'REJECTED' END,
        DECIDED_AT = CURRENT TIMESTAMP, DECIDED_BY = SESSION_USER
    WHERE SUGGESTION_ID = P_SUGGESTION_ID AND STATUS = 'PENDING';
  GET DIAGNOSTICS V_CLAIMED = ROW_COUNT;
  IF V_CLAIMED = 0 THEN
    SIGNAL SQLSTATE '75023' SET MESSAGE_TEXT = 'That suggestion was already decided';
  END IF;
  IF P_APPROVE = 0 THEN
    RETURN;
  END IF;

  SET V_BUS_START = (SELECT BUS_START FROM ASOF.POLICY_CLAUSE FOR BUSINESS_TIME AS OF V_FROM
                     WHERE CLAUSE_ID = V_CLAUSE AND VERSION_LABEL = V_VERSION);
  SELECT APPLIES_FROM, APPLIES_TO INTO V_OLD_FROM, V_OLD_TO FROM ASOF.PUBLISHED_ANSWER WHERE ANSWER_ID = V_ANSWER;

  IF V_OLD_FROM < V_FROM THEN
    -- Split: the old answer keeps its earlier dates; the correction gets its own row.
    SET V_NEW_ID = RTRIM(LEFT(V_ANSWER, 28)) || '-' || RTRIM(LEFT(V_VERSION, 3));  -- LEFT pads with blanks
    UPDATE ASOF.PUBLISHED_ANSWER SET APPLIES_TO = V_FROM, STATUS = 'LIVE' WHERE ANSWER_ID = V_ANSWER;
    INSERT INTO ASOF.PUBLISHED_ANSWER (ANSWER_ID, DOC_ID, QUESTION, ANSWER_TEXT, CITED_CLAUSE_ID, CITED_VERSION,
                                       CITED_BUS_START, APPLIES_FROM, APPLIES_TO, STATUS)
      SELECT V_NEW_ID, DOC_ID, QUESTION, V_TEXT, V_CLAUSE, V_VERSION, V_BUS_START, V_FROM, V_OLD_TO, 'LIVE'
      FROM ASOF.PUBLISHED_ANSWER WHERE ANSWER_ID = V_ANSWER;
    SET P_PUBLISHED_ID = V_NEW_ID;
  ELSE
    -- Stale for every date it covers: replace the text and the citation.
    UPDATE ASOF.PUBLISHED_ANSWER
      SET ANSWER_TEXT = V_TEXT, CITED_VERSION = V_VERSION, CITED_BUS_START = V_BUS_START, STATUS = 'LIVE'
      WHERE ANSWER_ID = V_ANSWER;
    SET P_PUBLISHED_ID = V_ANSWER;
  END IF;
  -- Any other pending suggestion for the same answer and date is now moot.
  UPDATE ASOF.ANSWER_SUGGESTION SET STATUS = 'REJECTED', DECIDED_AT = CURRENT TIMESTAMP, DECIDED_BY = SESSION_USER
    WHERE ANSWER_ID = V_ANSWER AND STATUS = 'PENDING' AND SUGGESTION_ID <> P_SUGGESTION_ID;
END
@

-- procedure: ADD_POLICY_DRAFT
-- Stores an uploaded policy document as a pending draft. Db2 computes the SHA-256 of the file itself
-- and refuses it if that differs from the hash the application computed, so the hash on record is
-- Db2's own. Granted to the policy editor only. The caller adds the items, then commits.
CREATE OR REPLACE PROCEDURE ASOF.ADD_POLICY_DRAFT (
    IN  P_DOC_ID    VARCHAR(32),
    IN  P_NAME      VARCHAR(200),
    IN  P_SHA256    CHAR(64),
    IN  P_PDF       BLOB(4M),
    IN  P_PAGES     SMALLINT,
    IN  P_TEXT      CLOB(256K),
    IN  P_MODEL     VARCHAR(200),
    IN  P_USER      VARCHAR(40),
    OUT P_DRAFT_ID  BIGINT)
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  DECLARE V_SHA CHAR(64);
  SET V_SHA = LOWER(HEX(CAST(HASH(P_PDF, 2) AS VARBINARY(32))));
  IF P_SHA256 IS NULL OR V_SHA <> P_SHA256 THEN
    SIGNAL SQLSTATE '75040' SET MESSAGE_TEXT = 'The file Db2 received does not match the SHA-256 the application computed';
  END IF;
  INSERT INTO ASOF.POLICY_DRAFT (DOC_ID, SOURCE_NAME, SOURCE_SHA256, SOURCE_PDF, SOURCE_PAGES, SOURCE_TEXT,
                                 EXTRACTED_BY, UPLOADED_BY)
    VALUES (P_DOC_ID, P_NAME, V_SHA, P_PDF, P_PAGES, P_TEXT, P_MODEL, NULLIF(P_USER, ''));
  SET P_DRAFT_ID = IDENTITY_VAL_LOCAL();
END
@

-- procedure: ADD_POLICY_DRAFT_ITEM
-- One proposed clause version of a pending draft. A CHANGE must name a clause the policy has; a NEW
-- clause must use an unused ID. The checks themselves run in asof/intake.py; their results and the
-- BLOCKED flag are stored with the item, and DECIDE_POLICY_DRAFT refuses to accept a blocked item.
CREATE OR REPLACE PROCEDURE ASOF.ADD_POLICY_DRAFT_ITEM (
    IN P_DRAFT_ID  BIGINT,
    IN P_ITEM_NO   SMALLINT,
    IN P_KIND      VARCHAR(10),
    IN P_CLAUSE_ID VARCHAR(32),
    IN P_AREA      VARCHAR(40),
    IN P_TITLE     VARCHAR(200),
    IN P_TEXT      VARCHAR(4000),
    IN P_RULE_JSON VARCHAR(2000),
    IN P_FROM      DATE,
    IN P_TO        DATE,
    IN P_QUOTE     VARCHAR(1000),
    IN P_PAGE      SMALLINT,
    IN P_CHECKS    VARCHAR(8000),
    IN P_BLOCKED   SMALLINT)
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  IF NOT EXISTS (SELECT 1 FROM ASOF.POLICY_DRAFT WHERE DRAFT_ID = P_DRAFT_ID AND STATUS = 'PENDING') THEN
    SIGNAL SQLSTATE '75041' SET MESSAGE_TEXT = 'Items can only be added to a pending draft';
  END IF;
  IF P_KIND = 'CHANGE' AND NOT EXISTS (SELECT 1 FROM ASOF.POLICY_CLAUSE WHERE CLAUSE_ID = P_CLAUSE_ID) THEN
    SIGNAL SQLSTATE '75011' SET MESSAGE_TEXT = 'Unknown clause';
  END IF;
  IF P_KIND = 'NEW' AND EXISTS (SELECT 1 FROM ASOF.POLICY_CLAUSE WHERE CLAUSE_ID = P_CLAUSE_ID) THEN
    SIGNAL SQLSTATE '75042' SET MESSAGE_TEXT = 'A new clause needs a clause ID the policy does not use yet';
  END IF;
  INSERT INTO ASOF.POLICY_DRAFT_ITEM (DRAFT_ID, ITEM_NO, KIND, CLAUSE_ID, AREA, TITLE, CLAUSE_TEXT, RULE_JSON,
                                      BUS_START, BUS_END, DATE_QUOTE, SOURCE_PAGE, CHECKS_JSON, BLOCKED)
    VALUES (P_DRAFT_ID, P_ITEM_NO, P_KIND, P_CLAUSE_ID, P_AREA, P_TITLE, P_TEXT, P_RULE_JSON,
            P_FROM, P_TO, P_QUOTE, NULLIF(P_PAGE, 0), P_CHECKS, P_BLOCKED);
END
@

-- procedure: DECIDE_POLICY_DRAFT
-- The policy editor approves a draft (with the items to accept, as a comma-separated list of item
-- numbers) or rejects it. Claims the draft atomically, so of two editors deciding at once exactly
-- one succeeds. A blocked or unchanged item cannot be accepted. When the draft records who uploaded
-- it (API users), the approver must be named and must be someone else. Approval only marks the
-- items: APPLY_DRAFT_ITEM puts each one into force in the same transaction. The caller commits.
CREATE OR REPLACE PROCEDURE ASOF.DECIDE_POLICY_DRAFT (
    IN  P_DRAFT_ID  BIGINT,
    IN  P_APPROVE   SMALLINT,
    IN  P_ACCEPT    VARCHAR(200),
    IN  P_USER      VARCHAR(40),
    OUT P_ACCEPTED  INTEGER)
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  DECLARE V_STATUS VARCHAR(12);
  DECLARE V_UPLOADER VARCHAR(40);
  DECLARE V_LIST VARCHAR(210);
  DECLARE V_LISTED INTEGER;
  DECLARE V_BAD INTEGER;
  DECLARE V_CLAIMED INTEGER;

  SET P_ACCEPTED = 0;
  SET V_LIST = ',' || REPLACE(COALESCE(P_ACCEPT, ''), ' ', '') || ',';
  SELECT STATUS, UPLOADED_BY INTO V_STATUS, V_UPLOADER FROM ASOF.POLICY_DRAFT WHERE DRAFT_ID = P_DRAFT_ID;
  IF V_STATUS IS NULL THEN
    SIGNAL SQLSTATE '75043' SET MESSAGE_TEXT = 'Unknown draft';
  END IF;
  IF P_APPROVE <> 0 AND V_UPLOADER IS NOT NULL AND (NULLIF(P_USER, '') IS NULL OR P_USER = V_UPLOADER) THEN
    SIGNAL SQLSTATE '75044' SET MESSAGE_TEXT = 'A policy document must be approved by someone other than the person who uploaded it';
  END IF;
  IF P_APPROVE <> 0 THEN
    SET V_LISTED = CASE WHEN V_LIST = ',,' THEN 0 ELSE LENGTH(V_LIST) - LENGTH(REPLACE(V_LIST, ',', '')) - 1 END;
    SET P_ACCEPTED = (SELECT COUNT(*) FROM ASOF.POLICY_DRAFT_ITEM WHERE DRAFT_ID = P_DRAFT_ID
                      AND LOCATE(',' || RTRIM(CHAR(ITEM_NO)) || ',', V_LIST) > 0);
    IF P_ACCEPTED = 0 THEN
      SIGNAL SQLSTATE '75046' SET MESSAGE_TEXT = 'Accept at least one item, or reject the draft';
    END IF;
    IF P_ACCEPTED <> V_LISTED THEN
      SIGNAL SQLSTATE '75045' SET MESSAGE_TEXT = 'The accepted items must be distinct items of this draft';
    END IF;
    SET V_BAD = (SELECT COUNT(*) FROM ASOF.POLICY_DRAFT_ITEM WHERE DRAFT_ID = P_DRAFT_ID
                 AND LOCATE(',' || RTRIM(CHAR(ITEM_NO)) || ',', V_LIST) > 0 AND (BLOCKED = 1 OR KIND = 'UNCHANGED'));
    IF V_BAD > 0 THEN
      SIGNAL SQLSTATE '75045' SET MESSAGE_TEXT = 'An item that failed a check, or changes nothing, cannot be accepted';
    END IF;
  END IF;

  UPDATE ASOF.POLICY_DRAFT
    SET STATUS = CASE WHEN P_APPROVE <> 0 THEN 'APPLIED' ELSE 'REJECTED' END,
        DECIDED_AT = CURRENT TIMESTAMP, DECIDED_BY = SESSION_USER, DECIDED_BY_USER = NULLIF(P_USER, '')
    WHERE DRAFT_ID = P_DRAFT_ID AND STATUS = 'PENDING';
  GET DIAGNOSTICS V_CLAIMED = ROW_COUNT;
  IF V_CLAIMED = 0 THEN
    SIGNAL SQLSTATE '75047' SET MESSAGE_TEXT = 'That draft was already decided';
  END IF;
  UPDATE ASOF.POLICY_DRAFT_ITEM
    SET STATUS = CASE WHEN P_APPROVE <> 0 AND LOCATE(',' || RTRIM(CHAR(ITEM_NO)) || ',', V_LIST) > 0
                      THEN 'APPLIED' ELSE 'REJECTED' END
    WHERE DRAFT_ID = P_DRAFT_ID;
END
@

-- procedure: APPLY_DRAFT_ITEM
-- Puts one accepted item of an approved draft into force, in the transaction that approved it: a
-- CHANGE through APPLY_POLICY_CHANGE (FOR PORTION OF BUSINESS_TIME), a NEW clause by INSERT. The
-- text, rule and dates come from the stored item, never from the caller, so this path applies only
-- what was reviewed, and only once. Db2 picks the next version label, and the clause row's change
-- note names the draft, the item and the file's SHA-256. P_EMBEDDING NULL: Db2 embeds the text with
-- the in-database model, as APPLY_POLICY_CHANGE does.
CREATE OR REPLACE PROCEDURE ASOF.APPLY_DRAFT_ITEM (
    IN  P_DRAFT_ID  BIGINT,
    IN  P_ITEM_NO   SMALLINT,
    IN  P_EMBEDDING VARCHAR(12000),
    OUT P_VERSION   VARCHAR(20),
    OUT P_ROWS      INTEGER,
    OUT P_FLAGGED   INTEGER)
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  DECLARE V_KIND VARCHAR(10);
  DECLARE V_CLAUSE VARCHAR(32);
  DECLARE V_AREA VARCHAR(40);
  DECLARE V_TITLE VARCHAR(200);
  DECLARE V_TEXT VARCHAR(4000);
  DECLARE V_RULE VARCHAR(2000);
  DECLARE V_FROM DATE;
  DECLARE V_TO DATE;
  DECLARE V_DOC VARCHAR(32);
  DECLARE V_NAME VARCHAR(200);
  DECLARE V_SHA CHAR(64);
  DECLARE V_NOTE VARCHAR(400);
  DECLARE V_VEC VECTOR(384, FLOAT32);
  DECLARE S_EMBED STATEMENT;
  DECLARE C_EMBED CURSOR FOR S_EMBED;

  SET P_ROWS = 0;
  SET P_FLAGGED = 0;
  SELECT I.KIND, I.CLAUSE_ID, I.AREA, I.TITLE, I.CLAUSE_TEXT, I.RULE_JSON, I.BUS_START, I.BUS_END,
         D.DOC_ID, D.SOURCE_NAME, D.SOURCE_SHA256
    INTO V_KIND, V_CLAUSE, V_AREA, V_TITLE, V_TEXT, V_RULE, V_FROM, V_TO, V_DOC, V_NAME, V_SHA
    FROM ASOF.POLICY_DRAFT_ITEM I JOIN ASOF.POLICY_DRAFT D ON D.DRAFT_ID = I.DRAFT_ID
    WHERE I.DRAFT_ID = P_DRAFT_ID AND I.ITEM_NO = P_ITEM_NO
      AND D.STATUS = 'APPLIED' AND I.STATUS = 'APPLIED' AND I.APPLIED_VERSION IS NULL;
  IF V_KIND IS NULL THEN
    SIGNAL SQLSTATE '75048' SET MESSAGE_TEXT = 'Only an accepted item of an approved draft can be applied, and only once';
  END IF;
  SET V_NOTE = RTRIM(LEFT('Policy intake: draft ' || RTRIM(CHAR(P_DRAFT_ID)) || ' item ' || RTRIM(CHAR(P_ITEM_NO))
                          || ', ' || V_NAME || ' (sha256 ' || LEFT(V_SHA, 16) || ')', 400));  -- LEFT pads

  IF V_KIND = 'CHANGE' THEN
    SET P_VERSION = 'v' || RTRIM(CHAR(1 + (SELECT COALESCE(MAX(INTEGER(SUBSTR(VERSION_LABEL, 2))), 0) FROM (
                      SELECT VERSION_LABEL FROM ASOF.POLICY_CLAUSE WHERE CLAUSE_ID = V_CLAUSE
                      UNION ALL
                      SELECT VERSION_LABEL FROM ASOF.POLICY_CLAUSE_HIST WHERE CLAUSE_ID = V_CLAUSE) AS L)));
    CALL ASOF.APPLY_POLICY_CHANGE(V_CLAUSE, V_FROM, V_TO, P_VERSION, V_TEXT, V_RULE, P_EMBEDDING, V_NOTE,
                                  P_ROWS, P_FLAGGED);
  ELSE
    IF EXISTS (SELECT 1 FROM ASOF.POLICY_CLAUSE WHERE CLAUSE_ID = V_CLAUSE) THEN
      SIGNAL SQLSTATE '75042' SET MESSAGE_TEXT = 'A new clause needs a clause ID the policy does not use yet';
    END IF;
    SET P_VERSION = 'v1';
    IF P_EMBEDDING IS NULL THEN
      BEGIN
        DECLARE EXIT HANDLER FOR SQLEXCEPTION
          SIGNAL SQLSTATE '75014' SET MESSAGE_TEXT = 'In-database embedding failed: no EMBEDDER model, or the endpoint refused';
        PREPARE S_EMBED FROM 'VALUES TO_EMBEDDING(CAST(? AS VARCHAR(4300)) USING ASOF.EMBEDDER)';
        OPEN C_EMBED USING V_TITLE || '. ' || V_TEXT;
        FETCH C_EMBED INTO V_VEC;
        CLOSE C_EMBED;
      END;
    ELSE
      SET V_VEC = VECTOR(P_EMBEDDING, 384, FLOAT32);
    END IF;
    INSERT INTO ASOF.POLICY_CLAUSE (CLAUSE_ID, DOC_ID, AREA, TITLE, VERSION_LABEL, CLAUSE_TEXT, RULE_JSON, EMBEDDING,
                                    CHANGE_NOTE, BUS_START, BUS_END)
      VALUES (V_CLAUSE, V_DOC, V_AREA, V_TITLE, P_VERSION, V_TEXT, V_RULE, V_VEC, V_NOTE, V_FROM, V_TO);
    SET P_ROWS = 1;
  END IF;
  UPDATE ASOF.POLICY_DRAFT_ITEM SET APPLIED_VERSION = P_VERSION WHERE DRAFT_ID = P_DRAFT_ID AND ITEM_NO = P_ITEM_NO;
END
@

-- procedure: RESOLVE_ESCALATION
-- A specialist answers a held decision (the review inbox, asof/review.py). The reply has been checked in
-- full against the clauses in force on the customer's date; this appends it to the hash-chained ledger as
-- a REVIEWED decision, through APPEND_LEDGER, and records which held decision it answers. The channel,
-- customer date and question are copied from the held row itself, so the reply cannot be filed against
-- another customer's question. Db2 refuses (and the caller rolls back):
--   75050 an unknown ledger row, 75051 one that was not held (only ESCALATED decisions are answered),
--   75052 one already answered, 75053 a reply checked against another policy document (allowed only
--   when the held decision's reason was that the document was uncertain, ROUTE_UNCERTAIN),
--   75054 a specialist answering a check they submitted themselves (with API users),
--   75055 a reply whose check found a contradiction, an unchecked detail or anything but a clean result,
--   75056 a reply the policy does not cover without the specialist's note (their judgment, on record),
--   75057 verdicts that do not match what is being recorded, 75030 a caller who cannot read ledger text.
-- The caller commits.
CREATE OR REPLACE PROCEDURE ASOF.RESOLVE_ESCALATION (
    IN  P_ESCALATED_ID   BIGINT,
    IN  P_REQUEST_ID     CHAR(36),
    IN  P_DOC_ID         VARCHAR(32),
    IN  P_REPLY          VARCHAR(4000),
    IN  P_FINAL          VARCHAR(4000),
    IN  P_CHECK_REASON   VARCHAR(40),
    IN  P_NOTE           VARCHAR(1000),
    IN  P_REVIEWER       VARCHAR(40),
    IN  P_MODEL          VARCHAR(200),
    IN  P_PROMPT_VERSION VARCHAR(40),
    IN  P_LATENCY_MS     INTEGER,
    IN  P_VERDICTS       VARCHAR(30000),
    OUT P_LEDGER_ID      BIGINT,
    OUT P_ROW_HASH       CHAR(64),
    OUT P_OUTCOME        VARCHAR(40))
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  DECLARE V_DECISION VARCHAR(12);
  DECLARE V_REASON VARCHAR(40);
  DECLARE V_CHANNEL VARCHAR(20);
  DECLARE V_DOC VARCHAR(32);
  DECLARE V_AS_OF DATE;
  DECLARE V_QUESTION VARCHAR(2000);
  DECLARE V_HELD_VERDICTS VARCHAR(30000);
  DECLARE V_REQUESTER VARCHAR(40);
  DECLARE V_CREATED TIMESTAMP(12);
  DECLARE V_CLAIMS INTEGER;
  DECLARE V_CONTRADICTED INTEGER;
  DECLARE V_UNCOVERED INTEGER;
  DECLARE V_NOTE VARCHAR(1000);
  DECLARE V_REVIEWER VARCHAR(40);

  IF VERIFY_ROLE_FOR_USER(SESSION_USER, 'ASOF_TEXT_READER') <> 1 THEN
    SIGNAL SQLSTATE '75030' SET MESSAGE_TEXT = 'RESOLVE_ESCALATION needs role ASOF_TEXT_READER: it copies the held question';
  END IF;
  -- Take the chain lock first (APPEND_LEDGER takes it too), so two specialists answering the same held
  -- decision queue here and the second one sees the first one's answer.
  UPDATE ASOF.CHAIN_HEAD SET LAST_LEDGER_ID = LAST_LEDGER_ID WHERE HEAD_ID = 1;

  SELECT DECISION, REASON_CODE, CHANNEL, DOC_ID, AS_OF_DATE, QUESTION_REDACTED, VERDICTS_JSON
    INTO V_DECISION, V_REASON, V_CHANNEL, V_DOC, V_AS_OF, V_QUESTION, V_HELD_VERDICTS
    FROM ASOF.ANSWER_LEDGER WHERE LEDGER_ID = P_ESCALATED_ID;
  IF V_DECISION IS NULL THEN
    SIGNAL SQLSTATE '75050' SET MESSAGE_TEXT = 'Unknown ledger entry';
  END IF;
  IF V_DECISION <> 'ESCALATED' THEN
    SIGNAL SQLSTATE '75051' SET MESSAGE_TEXT = 'Only a held (ESCALATED) decision goes to a specialist';
  END IF;
  IF EXISTS (SELECT 1 FROM ASOF.ESCALATION_REVIEW WHERE ESCALATED_LEDGER_ID = P_ESCALATED_ID) THEN
    SIGNAL SQLSTATE '75052' SET MESSAGE_TEXT = 'A specialist has already answered this decision';
  END IF;
  IF P_DOC_ID <> V_DOC AND V_REASON <> 'ROUTE_UNCERTAIN' THEN
    SIGNAL SQLSTATE '75053' SET MESSAGE_TEXT = 'The reply must be checked against the held decision''s policy document';
  END IF;
  -- '' (the driver binds no NULL here) means a local, unnamed specialist.
  SET V_REVIEWER = NULLIF(TRIM(COALESCE(P_REVIEWER, '')), '');
  SET V_REQUESTER = JSON_VALUE(V_HELD_VERDICTS, '$.requested_by' RETURNING VARCHAR(40));
  IF V_REVIEWER IS NOT NULL AND V_REQUESTER IS NOT NULL AND V_REVIEWER = V_REQUESTER THEN
    SIGNAL SQLSTATE '75054' SET MESSAGE_TEXT = 'A specialist cannot answer a check they submitted themselves';
  END IF;

  -- What the reply's check found, read from the verdicts that will be hashed into the chain.
  SELECT COUNT(*), COALESCE(SUM(CASE WHEN J.VERDICT = 'CONTRADICTED' THEN 1 ELSE 0 END), 0),
         COALESCE(SUM(CASE WHEN J.VERDICT = 'NOT_COVERED' THEN 1 ELSE 0 END), 0)
    INTO V_CLAIMS, V_CONTRADICTED, V_UNCOVERED
    FROM TABLE(ASOF.CLAIMS_FROM_JSON(P_VERDICTS)) AS J;
  IF EXISTS (SELECT 1 FROM TABLE(ASOF.CLAIMS_FROM_JSON(P_VERDICTS)) AS J WHERE J.PASS_NO <> 1)
     OR COALESCE(JSON_VALUE(P_VERDICTS, '$.review.of_ledger_id' RETURNING BIGINT), 0) <> P_ESCALATED_ID
     OR (P_CHECK_REASON = 'ALL_SUPPORTED' AND (V_CLAIMS = 0 OR V_UNCOVERED > 0))
     OR (P_CHECK_REASON = 'NO_POLICY_CLAIMS' AND V_CLAIMS > 0)
     OR (P_CHECK_REASON = 'NOT_COVERED' AND V_UNCOVERED = 0) THEN
    SIGNAL SQLSTATE '75057' SET MESSAGE_TEXT = 'The verdicts do not match the reply check being recorded';
  END IF;
  IF V_CONTRADICTED > 0 OR P_CHECK_REASON NOT IN ('ALL_SUPPORTED', 'NO_POLICY_CLAIMS', 'NOT_COVERED') THEN
    SIGNAL SQLSTATE '75055' SET MESSAGE_TEXT = 'The reply did not pass the check against the policy in force on the customer''s date: revise it';
  END IF;
  SET V_NOTE = NULLIF(TRIM(COALESCE(P_NOTE, '')), '');
  IF V_UNCOVERED > 0 AND LENGTH(COALESCE(V_NOTE, '')) < 10 THEN
    SIGNAL SQLSTATE '75056' SET MESSAGE_TEXT = 'No clause in force covers part of this reply: add a note that explains the specialist''s judgment';
  END IF;

  -- On the specialist's judgment: no clause covers part of the reply, or (asof/review.py) it talks policy but the
  -- check found no claim in it; both need the note. Otherwise every claim was supported (or there was none to check).
  IF COALESCE(JSON_VALUE(P_VERDICTS, '$.review.on_judgment' RETURNING VARCHAR(5)), 'false') = 'true'
     AND LENGTH(COALESCE(V_NOTE, '')) < 10 THEN
    SIGNAL SQLSTATE '75056' SET MESSAGE_TEXT = 'This reply goes out on the specialist''s judgment: add a note that explains it';
  END IF;
  SET P_OUTCOME = CASE WHEN V_UNCOVERED > 0
                         OR COALESCE(JSON_VALUE(P_VERDICTS, '$.review.on_judgment' RETURNING VARCHAR(5)), 'false') = 'true'
                       THEN 'SPECIALIST_JUDGMENT' ELSE 'SPECIALIST_CHECKED' END;
  CALL ASOF.APPEND_LEDGER_ROW(P_REQUEST_ID, V_CHANNEL, P_DOC_ID, V_AS_OF, V_QUESTION, P_REPLY, P_FINAL, 'REVIEWED',
                              P_OUTCOME, P_MODEL, P_PROMPT_VERSION, P_LATENCY_MS, P_VERDICTS,
                              P_LEDGER_ID, P_ROW_HASH, V_CREATED);
  INSERT INTO ASOF.ESCALATION_REVIEW (ESCALATED_LEDGER_ID, REVIEW_LEDGER_ID, OUTCOME, REVIEWER, NOTE)
    VALUES (P_ESCALATED_ID, P_LEDGER_ID, P_OUTCOME, V_REVIEWER, V_NOTE);
END
@

-- procedure: ADD_NOTICE
-- The change-impact agent stores a drafted correction notice (runtime user, EXECUTE only). Db2 checks the claims
-- the caller makes instead of taking them on trust:
--   75060 the answer is not a released decision (PASS, CORRECTED or REVIEWED) that cited this clause version,
--   75061 the version now in force for the customer's date is not CURRENT_VERSION (so the answer is not stale),
--   75062 the check named is not a ledger row for the same customer date and policy document, or its decision is
--         not the one claimed, or (for a released check) none of its released claims is supported by the new version,
--   23505 an open notice for this answer and version already exists (UX_NOTICE_OPEN).
CREATE OR REPLACE PROCEDURE ASOF.ADD_NOTICE (
    IN  P_LEDGER_ID       BIGINT,
    IN  P_CLAUSE_ID       VARCHAR(32),
    IN  P_CITED_VERSION   VARCHAR(20),
    IN  P_CURRENT_VERSION VARCHAR(20),
    IN  P_CORRECTION      VARCHAR(4000),
    IN  P_NOTICE          VARCHAR(6000),
    IN  P_CHECK_DECISION  VARCHAR(12),
    IN  P_CHECK_LEDGER_ID BIGINT,        -- 0 when the check left no ledger row
    IN  P_TRACE           VARCHAR(8000),
    IN  P_REQUESTED_BY    VARCHAR(40),   -- '' when no API user is named
    OUT P_NOTICE_ID       BIGINT)
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  DECLARE V_AS_OF DATE;
  DECLARE V_DOC VARCHAR(32);
  DECLARE V_IN_FORCE VARCHAR(20);
  DECLARE V_CHECK_DECISION VARCHAR(12);
  DECLARE V_CHECK_AS_OF DATE;
  DECLARE V_CHECK_DOC VARCHAR(32);

  SELECT L.AS_OF_DATE, L.DOC_ID INTO V_AS_OF, V_DOC
    FROM ASOF.ANSWER_LEDGER L
    WHERE L.LEDGER_ID = P_LEDGER_ID
      AND EXISTS (SELECT 1 FROM ASOF.CLAIM_CITATION C
                  WHERE C.LEDGER_ID = L.LEDGER_ID AND C.CLAUSE_ID = P_CLAUSE_ID AND C.CLAUSE_VERSION = P_CITED_VERSION
                    AND C.VERDICT = 'SUPPORTED'
                    AND ((L.DECISION IN ('PASS', 'REVIEWED') AND C.PASS_NO = 1)
                         OR (L.DECISION = 'CORRECTED' AND C.PASS_NO = 2)));
  IF V_AS_OF IS NULL THEN
    SIGNAL SQLSTATE '75060' SET MESSAGE_TEXT = 'That answer is not a released decision citing this clause version';
  END IF;
  SET V_IN_FORCE = (SELECT VERSION_LABEL FROM ASOF.POLICY_CLAUSE FOR BUSINESS_TIME AS OF V_AS_OF
                    WHERE CLAUSE_ID = P_CLAUSE_ID);
  IF V_IN_FORCE IS NULL OR V_IN_FORCE <> P_CURRENT_VERSION OR V_IN_FORCE = P_CITED_VERSION THEN
    SIGNAL SQLSTATE '75061' SET MESSAGE_TEXT = 'The version in force for the customer''s date is not the one named: the answer is not stale';
  END IF;
  IF P_CHECK_LEDGER_ID <> 0 THEN
    SELECT DECISION, AS_OF_DATE, DOC_ID INTO V_CHECK_DECISION, V_CHECK_AS_OF, V_CHECK_DOC
      FROM ASOF.ANSWER_LEDGER WHERE LEDGER_ID = P_CHECK_LEDGER_ID;
    IF V_CHECK_DECISION IS NULL OR V_CHECK_DECISION <> P_CHECK_DECISION OR V_CHECK_AS_OF <> V_AS_OF
       OR V_CHECK_DOC <> V_DOC THEN
      SIGNAL SQLSTATE '75062' SET MESSAGE_TEXT = 'The check named is not this correction''s check';
    END IF;
    IF P_CHECK_DECISION IN ('PASS', 'CORRECTED') AND NOT EXISTS (
         SELECT 1 FROM ASOF.CLAIM_CITATION C
         WHERE C.LEDGER_ID = P_CHECK_LEDGER_ID AND C.CLAUSE_ID = P_CLAUSE_ID AND C.CLAUSE_VERSION = P_CURRENT_VERSION
           AND C.VERDICT = 'SUPPORTED' AND C.PASS_NO = CASE WHEN P_CHECK_DECISION = 'CORRECTED' THEN 2 ELSE 1 END) THEN
      SIGNAL SQLSTATE '75062' SET MESSAGE_TEXT = 'The correction''s check found no claim supported by the version now in force';
    END IF;
  ELSEIF P_CHECK_DECISION <> 'ESCALATED' THEN
    SIGNAL SQLSTATE '75062' SET MESSAGE_TEXT = 'A released check must name its ledger row';
  END IF;
  INSERT INTO ASOF.CORRECTION_NOTICE (LEDGER_ID, CLAUSE_ID, CITED_VERSION, CURRENT_VERSION, AS_OF_DATE, CORRECTION_TEXT,
                                      NOTICE_TEXT, CHECK_DECISION, CHECK_LEDGER_ID, AGENT_TRACE, REQUESTED_BY)
    VALUES (P_LEDGER_ID, P_CLAUSE_ID, P_CITED_VERSION, P_CURRENT_VERSION, V_AS_OF, P_CORRECTION, P_NOTICE,
            P_CHECK_DECISION, NULLIF(P_CHECK_LEDGER_ID, 0), P_TRACE, NULLIF(TRIM(COALESCE(P_REQUESTED_BY, '')), ''));
  SET P_NOTICE_ID = IDENTITY_VAL_LOCAL();
END
@

-- procedure: DECIDE_NOTICE
-- A specialist approves a notice for sending (STATUS SENT) or rejects it. Exactly one decision per notice (75063
-- otherwise, the claim below is atomic). Approval needs a draft the check released (75064), and the policy for the
-- customer's date must not have changed again since the draft: if the version in force is no longer the one the
-- correction was checked against, it is refused (75065) and the agent drafts again.
CREATE OR REPLACE PROCEDURE ASOF.DECIDE_NOTICE (
    IN  P_NOTICE_ID BIGINT,
    IN  P_APPROVE   SMALLINT,
    IN  P_USER      VARCHAR(40))     -- '' when no API user is named
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  DECLARE V_STATUS VARCHAR(12);
  DECLARE V_DECISION VARCHAR(12);
  DECLARE V_CLAUSE VARCHAR(32);
  DECLARE V_VERSION VARCHAR(20);
  DECLARE V_AS_OF DATE;
  DECLARE V_IN_FORCE VARCHAR(20);
  DECLARE V_CLAIMED INTEGER;

  SELECT STATUS, CHECK_DECISION, CLAUSE_ID, CURRENT_VERSION, AS_OF_DATE
    INTO V_STATUS, V_DECISION, V_CLAUSE, V_VERSION, V_AS_OF
    FROM ASOF.CORRECTION_NOTICE WHERE NOTICE_ID = P_NOTICE_ID;
  IF V_STATUS IS NULL THEN
    SIGNAL SQLSTATE '75066' SET MESSAGE_TEXT = 'Unknown correction notice';
  END IF;
  IF P_APPROVE <> 0 THEN
    IF V_DECISION NOT IN ('PASS', 'CORRECTED') THEN
      SIGNAL SQLSTATE '75064' SET MESSAGE_TEXT = 'Only a notice whose correction the check released can be sent';
    END IF;
    SET V_IN_FORCE = (SELECT VERSION_LABEL FROM ASOF.POLICY_CLAUSE FOR BUSINESS_TIME AS OF V_AS_OF WHERE CLAUSE_ID = V_CLAUSE);
    IF V_IN_FORCE IS NULL OR V_IN_FORCE <> V_VERSION THEN
      SIGNAL SQLSTATE '75065' SET MESSAGE_TEXT = 'The policy for the customer''s date changed again since this notice was drafted: draft it again';
    END IF;
  END IF;
  UPDATE ASOF.CORRECTION_NOTICE
    SET STATUS = CASE WHEN P_APPROVE <> 0 THEN 'SENT' ELSE 'REJECTED' END,
        DECIDED_AT = CURRENT TIMESTAMP, DECIDED_BY = SESSION_USER,
        DECIDED_BY_USER = NULLIF(TRIM(COALESCE(P_USER, '')), '')
    WHERE NOTICE_ID = P_NOTICE_ID AND STATUS = 'PENDING';
  GET DIAGNOSTICS V_CLAIMED = ROW_COUNT;
  IF V_CLAIMED = 0 THEN
    SIGNAL SQLSTATE '75063' SET MESSAGE_TEXT = 'That notice was already decided';
  END IF;
END
@
