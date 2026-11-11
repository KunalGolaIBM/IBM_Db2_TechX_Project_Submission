-- Who stored each ledger row, as Db2 saw the session. Three columns, and a trigger that fills them on every
-- insert whatever the INSERT said, so a caller cannot supply its own values: APPEND_LEDGER_ROW's INSERT does not
-- name them, and an owner's direct INSERT that does is overwritten.
--
-- STORED_BY      SESSION_USER: the runtime user for the check's decisions, the reviewer user for a specialist's
--                reply (RESOLVE_ESCALATION), or the API user a trusted connection switched to.
--                CURRENT USER would not do: inside a procedure it is the procedure's owner.
-- STORED_ROLES   every role the session acted under, comma-separated: the roles VERIFY_ROLE_FOR_USER finds for
--                SESSION_USER (granted to it, its groups or PUBLIC, and roles nested in those), plus the
--                trusted context's role, which VERIFY_ROLE_FOR_USER does not report.
-- STORED_CONTEXT the trusted context the connection matched (MON_GET_CONNECTION), or NULL.
--
-- None of the three is in ROW_HASH, so VERIFY_CHAIN does not cover them: an owner who drops the triggers could
-- change them without breaking the chain. They are what Db2 recorded at insert time, protected by the append-only
-- triggers and the grants. MON_GET_CONNECTION and MON_GET_APPLICATION_HANDLE are built in and not fenced.
-- SECURED: Db2 requires it for a trigger on a table with column access control (05_masks.sql).

-- other: ANSWER_LEDGER_SESSION_COLUMNS
-- An ALTER, not part of the CREATE TABLE, so a ledger installed before these columns existed gets them too, rows and
-- hashes untouched (its older rows read NULL: not recorded). A column that exists already (SQLSTATE 42711) is
-- skipped. Adding a column marks the table's column masks invalid (SQL5188N on any later statement that reads a
-- masked column, CREATE PROCEDURE included); schema.install() creates them again right after this statement.
BEGIN
  DECLARE CONTINUE HANDLER FOR SQLSTATE '42711' BEGIN END;
  EXECUTE IMMEDIATE 'ALTER TABLE ASOF.ANSWER_LEDGER ADD COLUMN STORED_BY VARCHAR(128)';
  EXECUTE IMMEDIATE 'ALTER TABLE ASOF.ANSWER_LEDGER ADD COLUMN STORED_ROLES VARCHAR(1000)';
  EXECUTE IMMEDIATE 'ALTER TABLE ASOF.ANSWER_LEDGER ADD COLUMN STORED_CONTEXT VARCHAR(128)';
END
@

-- trigger: ANSWER_LEDGER_SESSION_AUDIT
CREATE OR REPLACE TRIGGER ASOF.ANSWER_LEDGER_SESSION_AUDIT
  NO CASCADE BEFORE INSERT ON ASOF.ANSWER_LEDGER
  REFERENCING NEW AS N
  FOR EACH ROW SECURED
  BEGIN ATOMIC
    DECLARE V_CTX VARCHAR(128);
    DECLARE V_CTX_ROLE VARCHAR(128);
    SET (V_CTX, V_CTX_ROLE) = (SELECT NULLIF(TRIM(M.TRUSTED_CTX_NAME), ''), NULLIF(TRIM(M.TRUSTED_CTX_ROLE), '')
                               FROM TABLE(MON_GET_CONNECTION(MON_GET_APPLICATION_HANDLE(), -1)) AS M
                               FETCH FIRST 1 ROW ONLY);
    SET N.STORED_BY = SESSION_USER;
    SET N.STORED_CONTEXT = V_CTX;
    SET N.STORED_ROLES = (SELECT CAST(LISTAGG(DISTINCT R.ROLE_NAME, ',') WITHIN GROUP (ORDER BY R.ROLE_NAME)
                                      AS VARCHAR(1000))
                          FROM (SELECT CAST(ROLENAME AS VARCHAR(128)) AS ROLE_NAME FROM SYSCAT.ROLES
                                  WHERE VERIFY_ROLE_FOR_USER(SESSION_USER, ROLENAME) = 1
                                UNION ALL
                                SELECT V_CTX_ROLE FROM SYSIBM.SYSDUMMY1 WHERE V_CTX_ROLE IS NOT NULL
                                ORDER BY 1 FETCH FIRST 30 ROWS ONLY) AS R);  -- 30 names always fit LISTAGG
  END
@
