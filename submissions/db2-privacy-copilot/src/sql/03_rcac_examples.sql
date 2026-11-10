-- RCAC (Row and Column Access Control) examples for Phase 7 (stretch)
-- These are example policies; they must be reviewed by a SECADM user before application

-- Example: Column mask for phone numbers
-- Only users with DOCTOR role can see full phone numbers; others see masked version
/*
CREATE MASK PHONE_MASK ON PATIENT FOR COLUMN PH_NO
RETURN CASE 
    WHEN VERIFY_ROLE_FOR_USER(SESSION_USER, 'DOCTOR') = 1 THEN PH_NO
    ELSE 999999999
END
ENABLE;
*/

-- Example: Column mask for email addresses
/*
CREATE MASK EMAIL_MASK ON PATIENT FOR COLUMN CUST_MAIL_ID
RETURN CASE 
    WHEN VERIFY_ROLE_FOR_USER(SESSION_USER, 'DOCTOR') = 1 
         OR VERIFY_ROLE_FOR_USER(SESSION_USER, 'DPO') = 1
    THEN CUST_MAIL_ID
    ELSE 'REDACTED@REDACTED.COM'
END
ENABLE;
*/

-- Example: Row permission to restrict access to patients
/*
CREATE PERMISSION PATIENT_ROW_ACCESS ON PATIENT
FOR ROWS WHERE 
    VERIFY_ROLE_FOR_USER(SESSION_USER, 'DOCTOR') = 1
    OR VERIFY_ROLE_FOR_USER(SESSION_USER, 'DPO') = 1
    OR VERIFY_ROLE_FOR_USER(SESSION_USER, 'ADMIN') = 1
ENFORCED FOR ALL ACCESS
ENABLE;
*/

-- To activate RCAC (requires SECADM authority):
-- ALTER TABLE PATIENT ACTIVATE COLUMN ACCESS CONTROL;
-- ALTER TABLE PATIENT ACTIVATE ROW ACCESS CONTROL;

-- Note: These are examples only and must be:
-- 1. Reviewed by legal and security teams
-- 2. Applied by a user with SECADM authority
-- 3. Tested thoroughly before production use
