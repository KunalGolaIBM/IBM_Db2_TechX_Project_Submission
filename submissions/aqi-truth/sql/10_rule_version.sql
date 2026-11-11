-- Business time (application time) for the CPCB rule settings. Add-only: nothing existing is changed.
-- AQ.SETTING holds the values the audit procedures read today. AQ.RULE_VERSION keeps every version of those values with
-- the period of the readings it applies to (PERIOD BUSINESS_TIME), and Db2 refuses two versions of one setting for the
-- same days (BUSINESS_TIME WITHOUT OVERLAPS). When CPCB changes a rule (say, the minimum valid hours for a 24-hour
-- average), the new value is written with UPDATE ... FOR PORTION OF BUSINESS_TIME,
-- and FOR BUSINESS_TIME AS OF <day> returns the rule that applies to that day's readings.
-- With AQ.READING (system time) this makes the audit bitemporal: what the data said when, and which rule applied to which day.
-- Undo: sql/10_undo.sql.
CREATE TABLE AQ.RULE_VERSION (
  NAME      VARCHAR(30)  NOT NULL,
  NUM_VALUE DOUBLE       NOT NULL,
  NOTE      VARCHAR(300) NOT NULL,
  SOURCE    VARCHAR(200) NOT NULL,
  EFF_FROM  DATE         NOT NULL,
  EFF_TO    DATE         NOT NULL,
  PERIOD BUSINESS_TIME (EFF_FROM, EFF_TO),
  PRIMARY KEY (NAME, BUSINESS_TIME WITHOUT OVERLAPS)
)@
-- The version in force for every audited day: the current settings, applied from the first audited day (1 Sep 2025).
INSERT INTO AQ.RULE_VERSION (NAME, NUM_VALUE, NOTE, SOURCE, EFF_FROM, EFF_TO)
  SELECT S.NAME, S.NUM_VALUE, S.NOTE, 'CPCB National Air Quality Index (2014), as applied by this audit', '2025-09-01', '9999-12-31'
  FROM AQ.SETTING S
  WHERE NOT EXISTS (SELECT 1 FROM AQ.RULE_VERSION R WHERE R.NAME = S.NAME)@
