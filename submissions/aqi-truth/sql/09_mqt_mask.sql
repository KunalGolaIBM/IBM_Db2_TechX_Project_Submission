-- Add-only, 10 Nov 2026. Two Db2 features on top of the loaded schema; neither changes a stored row.
-- Undo (one line each, tested): sql/09_undo.sql

-- 1. Materialized query table: readings per station, pollutant and day (the data-capture summary).
--    REFRESH DEFERRED + ENABLE QUERY OPTIMIZATION: with CURRENT REFRESH AGE ANY the optimizer rewrites matching
--    queries on AQ.READING to read this small table instead (EXPLAIN in scripts/db2_evidence.py shows it).
--    The loader refreshes it after each load (REFRESH TABLE), so its age is the age of the last load.
CREATE TABLE AQ.MQT_READING_DAY AS (
  SELECT STATION_ID, PARAM, DATE(TS) AS DAY, COUNT(*) AS N_ROWS, COUNT(VALUE) AS N_VALUES, SUM(VALUE) AS SUM_VALUE, MAX(VALUE) AS MAX_VALUE
    FROM AQ.READING
   GROUP BY STATION_ID, PARAM, DATE(TS))
  DATA INITIALLY DEFERRED REFRESH DEFERRED ENABLE QUERY OPTIMIZATION MAINTAINED BY SYSTEM@
REFRESH TABLE AQ.MQT_READING_DAY@
GRANT SELECT ON AQ.MQT_READING_DAY TO USER AQAPP@

-- 2. Column mask: visitors type free text into the question box, and the site lists recent questions publicly.
--    Db2 redacts e-mail addresses (\x{40} is the at sign, which ends statements in this file) and phone numbers in AQ.ASK_LOG.QUESTION for every ID except the auditor role
--    (and the instance owners). Stored text is unchanged; lookups on QNORM are unaffected.
CREATE OR REPLACE MASK AQ.ASK_QUESTION_MASK ON AQ.ASK_LOG FOR COLUMN QUESTION RETURN
  CASE WHEN VERIFY_ROLE_FOR_USER(SESSION_USER, 'AQAUDITOR') = 1 OR VERIFY_GROUP_FOR_USER(SESSION_USER, 'DB2IADM1') = 1 THEN QUESTION
       ELSE REGEXP_REPLACE(REGEXP_REPLACE(QUESTION, '[A-Za-z0-9._%+-]+\x{40}[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[e-mail removed]'),
                           '(\+?91[ -]?)?[6-9][0-9]{9}|[0-9]{10,}', '[number removed]') END
  ENABLE@
ALTER TRIGGER AQ.ASK_LOG_NO_UPDATE SECURED@
ALTER TRIGGER AQ.ASK_LOG_NO_DELETE SECURED@
ALTER TABLE AQ.ASK_LOG ACTIVATE COLUMN ACCESS CONTROL@
