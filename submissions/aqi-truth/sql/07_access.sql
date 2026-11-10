-- Row access control (RCAC). The US Embassy monitor (OpenAQ 8118) measures PM2.5 only, so CPCB's AQI never
-- applies to it and it is outside the audit's scope. Db2 itself hides its verdict rows from every ID except holders of
-- the AQAUDITOR role or the instance administrators' group (the loader runs as the instance owner, which cannot grant
-- a role to itself), whatever SQL they write. V_DAY's own filter is kept as the readable statement of the rule.
CREATE ROLE AQAUDITOR@
CREATE OR REPLACE PERMISSION AQ.VERDICT_SCOPE ON AQ.VERDICT
  FOR ROWS WHERE STATION_ID <> 8118
              OR VERIFY_ROLE_FOR_USER(SESSION_USER, 'AQAUDITOR') = 1
              OR VERIFY_GROUP_FOR_USER(SESSION_USER, 'DB2IADM1') = 1
  ENFORCED FOR ALL ACCESS ENABLE@
-- Triggers on a table under row access control must be SECURED (reviewed as trusted by the security admin).
ALTER TRIGGER AQ.VERDICT_NO_UPDATE SECURED@
ALTER TRIGGER AQ.VERDICT_NO_DELETE SECURED@
ALTER TABLE AQ.VERDICT ACTIVATE ROW ACCESS CONTROL@
