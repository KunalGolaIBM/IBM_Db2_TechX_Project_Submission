-- Db2 workload management for model-generated SQL. See docs/wlm.md.
--
-- "Ask the ledger" runs SQL a language model wrote, as a read-only analyst user, after askledger.validate has
-- accepted it. The validator decides what a query may read; it cannot tell how expensive a valid query is. So every
-- analyst connection (role ASOF_ANALYST: asofread and the domain analysts) lands in its own Db2 workload, whose
-- thresholds let Db2 itself stop a runaway query, whoever wrote it and whatever client sent it:
--   TH_ASOF_ANALYST_COST  the optimizer's estimate is over the limit: refused before it runs (SQL4712N reason 7)
--   TH_ASOF_ANALYST_ROWS  more rows returned than the limit: stopped at that row (reason 8)
--   TH_ASOF_ANALYST_TIME  running longer than the limit: stopped (reason 9)
-- All three answer SQLSTATE 5U026; asof/wlm.py turns that into the refusal Ask the ledger shows.
-- The limits are far above anything the Ask page's examples or the tests need (docs/wlm.md has the measurements),
-- and asof/wlm.py holds the same numbers (a test keeps them in step, and one checks the live catalog).
--
-- These are database-level objects, shared by every AsOf schema (ASOF, ASOF_TEST, ...), like the roles and the
-- 32K tablespace: each statement is skipped when the object exists, and dropping a schema leaves them alone.
-- `python -m asof.wlm --drop` removes them. To change a limit on a database that has them: ALTER THRESHOLD.

-- role: ASOF_ANALYST
-- Created here, before the grants file, because CREATE WORKLOAD checks that the role exists (SQL0204N).
CREATE ROLE ASOF_ANALYST
@

-- workload: WL_ASOF_ANALYST
-- Every connection whose session user holds ASOF_ANALYST, once it has USAGE (90_grants.sql). Everyone else keeps
-- Db2's default user workload, with no AsOf thresholds.
CREATE WORKLOAD WL_ASOF_ANALYST SESSION_USER ROLE ('ASOF_ANALYST') ENABLE
@

-- threshold: TH_ASOF_ANALYST_COST
CREATE THRESHOLD TH_ASOF_ANALYST_COST FOR WORKLOAD WL_ASOF_ANALYST ACTIVITIES ENFORCEMENT DATABASE
  WHEN ESTIMATEDSQLCOST > 1000000 STOP EXECUTION
@

-- threshold: TH_ASOF_ANALYST_ROWS
CREATE THRESHOLD TH_ASOF_ANALYST_ROWS FOR WORKLOAD WL_ASOF_ANALYST ACTIVITIES ENFORCEMENT DATABASE
  WHEN SQLROWSRETURNED > 10000 STOP EXECUTION
@

-- threshold: TH_ASOF_ANALYST_TIME
-- Db2 takes this limit in multiples of 10 seconds (15 SECONDS is SQL0644N) and checks it periodically, so a query
-- stops a little after the limit (11 s in the spike).
CREATE THRESHOLD TH_ASOF_ANALYST_TIME FOR WORKLOAD WL_ASOF_ANALYST ACTIVITIES ENFORCEMENT DATABASE
  WHEN ACTIVITYTOTALTIME > 10 SECONDS STOP EXECUTION
@
