-- Row and column access control (RCAC) on the ledger's free text.
--
-- The customer's question, the draft, the released answer and the full verdict JSON are shown
-- only to users holding the ASOF_TEXT_READER role: the runtime user, which writes and verifies
-- the ledger. Everyone else, including the owner, the policy editor, the read-only analyst and
-- any user added later, gets '[masked]'. Db2 applies the masks to every query, through every
-- view, whoever wrote it, so "Ask the ledger" cannot see the text even if its SQL tried to.
--
-- Db2 applies masks to returned values, not to predicates: an analyst who could write
-- WHERE FINAL_ANSWER LIKE '%...%' would learn something from the row count. The analyst user
-- only reaches Db2 through "Ask the ledger", whose validator (asof/askledger.py) allows these
-- columns as plain output columns only. See "Security" in architecture.md.

-- mask: M_LEDGER_QUESTION
CREATE OR REPLACE MASK ASOF.M_LEDGER_QUESTION ON ASOF.ANSWER_LEDGER FOR COLUMN QUESTION_REDACTED
  RETURN CASE WHEN VERIFY_ROLE_FOR_USER(SESSION_USER, 'ASOF_TEXT_READER') = 1 THEN QUESTION_REDACTED
              ELSE '[masked]' END
  ENABLE
@

-- mask: M_LEDGER_DRAFT
CREATE OR REPLACE MASK ASOF.M_LEDGER_DRAFT ON ASOF.ANSWER_LEDGER FOR COLUMN DRAFT_REDACTED
  RETURN CASE WHEN VERIFY_ROLE_FOR_USER(SESSION_USER, 'ASOF_TEXT_READER') = 1 THEN DRAFT_REDACTED
              ELSE '[masked]' END
  ENABLE
@

-- mask: M_LEDGER_FINAL
CREATE OR REPLACE MASK ASOF.M_LEDGER_FINAL ON ASOF.ANSWER_LEDGER FOR COLUMN FINAL_ANSWER
  RETURN CASE WHEN VERIFY_ROLE_FOR_USER(SESSION_USER, 'ASOF_TEXT_READER') = 1 THEN FINAL_ANSWER
              ELSE '[masked]' END
  ENABLE
@

-- mask: M_LEDGER_VERDICTS
CREATE OR REPLACE MASK ASOF.M_LEDGER_VERDICTS ON ASOF.ANSWER_LEDGER FOR COLUMN VERDICTS_JSON
  RETURN CASE WHEN VERIFY_ROLE_FOR_USER(SESSION_USER, 'ASOF_TEXT_READER') = 1 THEN VERDICTS_JSON
              ELSE '{"masked": true}' END
  ENABLE
@

-- other: ACTIVATE_LEDGER_COLUMN_ACCESS
ALTER TABLE ASOF.ANSWER_LEDGER ACTIVATE COLUMN ACCESS CONTROL
@

-- mask: P_MQT_DECISION_STATS_ALL_ROWS
-- Activating column access control on ANSWER_LEDGER makes Db2 activate row access control on every
-- materialized query table built over it, with no permission defined: every row hidden, from everyone.
-- MQT_DECISION_STATS holds only counts and latency sums per channel, decision and reason, none of the
-- masked text, so every user who can read it (through V_DECISION_STATS) may see every row.
CREATE OR REPLACE PERMISSION ASOF.P_MQT_DECISION_STATS_ALL_ROWS ON ASOF.MQT_DECISION_STATS
  FOR ROWS WHERE 1 = 1 ENFORCED FOR ALL ACCESS ENABLE
@
