-- Undo for sql/09_mqt_mask.sql. Removes only what 09 added; no stored row is touched.
-- After undo the (inactive) mask definition and the SECURED flag on the two ASK_LOG triggers remain; both are harmless while column access control is off.
ALTER TABLE AQ.ASK_LOG DEACTIVATE COLUMN ACCESS CONTROL@
DROP TABLE AQ.MQT_READING_DAY@
