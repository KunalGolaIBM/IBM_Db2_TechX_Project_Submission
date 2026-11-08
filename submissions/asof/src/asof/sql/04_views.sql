-- Views for the policy timeline and analytics. The runtime user reads these with SELECT.

-- view: V_POLICY_TIMELINE
-- Every clause version with its key rule parameters as relational columns, read out of
-- RULE_JSON with JSON_TABLE. This is how the timeline shows "first bag $35 -> $40".
CREATE OR REPLACE VIEW ASOF.V_POLICY_TIMELINE AS
  SELECT C.CLAUSE_ID, C.DOC_ID, C.AREA, C.TITLE, C.VERSION_LABEL, C.BUS_START, C.BUS_END,
         C.CHANGED_BY, C.CHANGE_NOTE, C.SYS_START, C.CLAUSE_TEXT, C.RULE_JSON,
         J.FIRST_BAG_FEE_USD, J.SECOND_BAG_FEE_USD, J.CHANGE_FEE_USD, J.PET_FEE_USD, J.CANCELLATION_FEE_USD,
         J.COMPENSATION_USD, J.DISCOUNT_PCT, J.REQUEST_WINDOW_DAYS, J.FREE_CANCEL_WINDOW_HOURS,
         J.MIN_DAYS_BEFORE_DEPARTURE, J.CREDIT_VALIDITY_MONTHS, J.MAX_PASSENGERS, J.RETROACTIVE_ALLOWED,
         J.TRANSFER_ALLOWED, J.CHANGES_ALLOWED
  FROM ASOF.POLICY_CLAUSE C,
       JSON_TABLE(C.RULE_JSON, 'strict $'
         COLUMNS (FIRST_BAG_FEE_USD         DECIMAL(9, 2) PATH '$.first_bag_fee_usd',
                  SECOND_BAG_FEE_USD        DECIMAL(9, 2) PATH '$.second_bag_fee_usd',
                  CHANGE_FEE_USD            DECIMAL(9, 2) PATH '$.change_fee_usd',
                  PET_FEE_USD               DECIMAL(9, 2) PATH '$.pet_fee_usd',
                  CANCELLATION_FEE_USD      DECIMAL(9, 2) PATH '$.cancellation_fee_usd',
                  COMPENSATION_USD          DECIMAL(9, 2) PATH '$.compensation_usd',
                  DISCOUNT_PCT              DECIMAL(5, 2) PATH '$.discount_pct',
                  REQUEST_WINDOW_DAYS       INTEGER       PATH '$.request_window_days',
                  FREE_CANCEL_WINDOW_HOURS  INTEGER       PATH '$.free_cancel_window_hours',
                  MIN_DAYS_BEFORE_DEPARTURE INTEGER       PATH '$.min_days_before_departure',
                  CREDIT_VALIDITY_MONTHS    INTEGER       PATH '$.credit_validity_months',
                  MAX_PASSENGERS            INTEGER       PATH '$.max_passengers',
                  RETROACTIVE_ALLOWED       VARCHAR(5)    PATH '$.retroactive_allowed',
                  TRANSFER_ALLOWED          VARCHAR(5)    PATH '$.transfer_allowed',
                  CHANGES_ALLOWED           VARCHAR(5)    PATH '$.changes_allowed')
         ERROR ON ERROR) AS J
@

-- Materialized query tables behind the analytics views. REFRESH IMMEDIATE: Db2 updates them in the same
-- transaction as every insert into the base table, so they are never stale, and setup refreshes each one
-- right after creating it (until then Db2 refuses inserts into the base table). The optimizer may also use
-- them for queries that do not name them (ENABLE QUERY OPTIMIZATION).

-- mqt: MQT_DECISION_STATS
CREATE TABLE ASOF.MQT_DECISION_STATS AS (
  SELECT CHANNEL, DECISION, REASON_CODE, COUNT(*) AS DECISIONS, SUM(BIGINT(LATENCY_MS)) AS LATENCY_MS_SUM
  FROM ASOF.ANSWER_LEDGER
  GROUP BY CHANNEL, DECISION, REASON_CODE)
  DATA INITIALLY DEFERRED REFRESH IMMEDIATE ENABLE QUERY OPTIMIZATION MAINTAINED BY SYSTEM IN ASOF_TS32K
@

-- mqt: MQT_CLAIM_OUTCOMES
CREATE TABLE ASOF.MQT_CLAIM_OUTCOMES AS (
  SELECT PASS_NO, AREA,
         SUM(CASE WHEN VERDICT = 'SUPPORTED' THEN 1 ELSE 0 END)    AS SUPPORTED,
         SUM(CASE WHEN VERDICT = 'CONTRADICTED' THEN 1 ELSE 0 END) AS CONTRADICTED,
         SUM(CASE WHEN VERDICT = 'NOT_COVERED' THEN 1 ELSE 0 END)  AS NOT_COVERED,
         COUNT(*) AS CLAIMS
  FROM ASOF.CLAIM_CITATION
  GROUP BY PASS_NO, AREA)
  DATA INITIALLY DEFERRED REFRESH IMMEDIATE ENABLE QUERY OPTIMIZATION MAINTAINED BY SYSTEM IN ASOF_TS32K
@

-- view: V_DECISION_STATS
-- Counts and mean latency from MQT_DECISION_STATS (one row per group, whatever the ledger's size); the first
-- and last time of each group from the ends of IX_LEDGER_GROUP_CREATED. Same columns and values as the
-- GROUP BY over the whole ledger it replaced.
CREATE OR REPLACE VIEW ASOF.V_DECISION_STATS AS
  SELECT M.CHANNEL, M.DECISION, M.REASON_CODE, M.DECISIONS,
         INTEGER(M.LATENCY_MS_SUM / M.DECISIONS) AS AVG_LATENCY_MS,
         (SELECT MIN(L.CREATED_AT) FROM ASOF.ANSWER_LEDGER L
          WHERE L.CHANNEL = M.CHANNEL AND L.DECISION = M.DECISION AND L.REASON_CODE = M.REASON_CODE) AS FIRST_AT,
         (SELECT MAX(L.CREATED_AT) FROM ASOF.ANSWER_LEDGER L
          WHERE L.CHANNEL = M.CHANNEL AND L.DECISION = M.DECISION AND L.REASON_CODE = M.REASON_CODE) AS LAST_AT
  FROM ASOF.MQT_DECISION_STATS M
@

-- view: V_CLAIM_OUTCOMES_BY_AREA
-- Verdicts on the drafts as they arrived (PASS_NO 1), by policy area.
-- Read from MQT_CLAIM_OUTCOMES: one row per pass and area instead of a scan of every citation.
CREATE OR REPLACE VIEW ASOF.V_CLAIM_OUTCOMES_BY_AREA AS
  SELECT AREA, SUPPORTED, CONTRADICTED, NOT_COVERED, CLAIMS
  FROM ASOF.MQT_CLAIM_OUTCOMES
  WHERE PASS_NO = 1
@

-- view: V_RULE_OVERRIDES
-- Claims where the deterministic rule check overruled the LLM judge's SUPPORTED.
CREATE OR REPLACE VIEW ASOF.V_RULE_OVERRIDES AS
  SELECT L.LEDGER_ID, L.CREATED_AT, L.AS_OF_DATE, L.DECISION, C.PASS_NO, C.CLAIM_NO, C.CLAIM_TEXT,
         C.CLAUSE_ID, C.CLAUSE_VERSION
  FROM ASOF.CLAIM_CITATION C
  JOIN ASOF.ANSWER_LEDGER L ON L.LEDGER_ID = C.LEDGER_ID
  WHERE C.LLM_VERDICT = 'SUPPORTED' AND C.VERDICT = 'CONTRADICTED' AND C.RULE_CHECK = 'MISMATCH'
@

-- The audit views below are the only objects the read-only analyst (role ASOF_ANALYST) can
-- query, and the only ones "Ask the ledger" may name. They carry decisions, verdicts and the
-- clause versions cited. QUESTION_REDACTED and FINAL_ANSWER are included so the analyst can
-- see that they exist, but the column masks in 05_masks.sql return '[masked]' for anyone
-- without the ASOF_TEXT_READER role.

-- view: V_AUDIT_DECISIONS
-- One row per decision.
CREATE OR REPLACE VIEW ASOF.V_AUDIT_DECISIONS AS
  SELECT L.LEDGER_ID, L.CREATED_AT, L.CHANNEL, L.DOC_ID, L.AS_OF_DATE, L.DECISION, L.REASON_CODE,
         L.MODEL_INFO, L.PROMPT_VERSION, L.LATENCY_MS,
         (SELECT COUNT(*) FROM ASOF.CLAIM_CITATION C WHERE C.LEDGER_ID = L.LEDGER_ID AND C.PASS_NO = 1) AS CLAIMS,
         (SELECT COUNT(*) FROM ASOF.CLAIM_CITATION C
           WHERE C.LEDGER_ID = L.LEDGER_ID AND C.PASS_NO = 1 AND C.VERDICT = 'CONTRADICTED') AS CONTRADICTED_CLAIMS,
         L.QUESTION_REDACTED, L.FINAL_ANSWER
  FROM ASOF.ANSWER_LEDGER L
@

-- view: V_AUDIT_CLAIMS
-- One row per checked claim, with the decision it fed into and the exact clause version cited.
CREATE OR REPLACE VIEW ASOF.V_AUDIT_CLAIMS AS
  SELECT C.LEDGER_ID, L.CREATED_AT, L.CHANNEL, L.AS_OF_DATE, L.DECISION, C.PASS_NO, C.CLAIM_NO, C.AREA,
         C.CLAIM_TEXT, C.VERDICT, C.LLM_VERDICT, C.RULE_CHECK, C.CLAUSE_ID, C.CLAUSE_VERSION,
         C.CLAUSE_BUS_START, C.DISTANCE
  FROM ASOF.CLAIM_CITATION C
  JOIN ASOF.ANSWER_LEDGER L ON L.LEDGER_ID = C.LEDGER_ID
@
