-- Session temp space used by COMPUTE_AQI_AUDITED's declared temporary table.
CREATE USER TEMPORARY TABLESPACE AQ_TEMP@
-- SYSTOOLSPACE holds the error tables of SYSPROC.ADMIN_DROP_SCHEMA (used by eval/fault_injection.py and a
-- full rebuild); a fresh Db2 database does not have it. Each statement here may already exist (SQL0601N).
CREATE TABLESPACE SYSTOOLSPACE IN IBMCATGROUP MANAGED BY AUTOMATIC STORAGE EXTENTSIZE 4@
