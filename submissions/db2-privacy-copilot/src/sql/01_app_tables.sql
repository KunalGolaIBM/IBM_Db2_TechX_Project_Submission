-- Application tables for the Privacy Copilot system

-- PII classification map
CREATE TABLE PII_MAP (
    ID             INT NOT NULL PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    TABNAME        VARCHAR(128) NOT NULL,
    COLNAME        VARCHAR(128) NOT NULL,
    LABEL          VARCHAR(40) NOT NULL,     -- EMAIL, PHONE, DOB, AADHAAR, PAN, etc.
    CONFIDENCE     DECIMAL(5,4) NOT NULL,    -- 0.0 to 1.0
    METHOD         VARCHAR(20) NOT NULL,      -- VALUE_RULE, NAME_VECTOR, NAME_HEURISTIC
    REVIEWED_BY    VARCHAR(100),
    REVIEWED_AT    TIMESTAMP,
    CLASSIFIED_AT  TIMESTAMP DEFAULT CURRENT TIMESTAMP,
    UNIQUE (TABNAME, COLNAME)
);

-- Retention rules (curated by hand)
CREATE TABLE RETENTION_RULES (
    TABNAME        VARCHAR(128) NOT NULL PRIMARY KEY,
    ACTION         VARCHAR(10) NOT NULL CHECK (ACTION IN ('ERASE', 'ANONYMISE', 'RETAIN')),
    REASON         VARCHAR(200) NOT NULL,
    SOURCE         VARCHAR(150) NOT NULL,
    VERIFIED       CHAR(1) NOT NULL DEFAULT 'N' CHECK (VERIFIED IN ('Y', 'N'))
);

-- Rights requests (erasure, access, etc.)
CREATE TABLE REQUESTS (
    ID             INT NOT NULL PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    REQUEST_TYPE   VARCHAR(20) NOT NULL CHECK (REQUEST_TYPE IN ('ERASURE', 'ACCESS', 'PORTABILITY')),
    SUBJECT_ID     INT NOT NULL,          -- FK to PATIENT.ID
    STATUS         VARCHAR(20) NOT NULL DEFAULT 'RECEIVED' 
                   CHECK (STATUS IN ('RECEIVED', 'PLANNING', 'PENDING_APPROVAL', 'APPROVED', 'COMPLETED', 'REJECTED', 'FAILED')),
    RECEIVED_AT    TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    DUE_AT         TIMESTAMP NOT NULL,
    PLAN_JSON      CLOB,                  -- JSON of the execution plan
    PLAN_HASH      VARCHAR(64),           -- SHA256 of plan for approval binding
    APPROVED_BY    VARCHAR(100),
    APPROVED_AT    TIMESTAMP,
    APPROVAL_ID    VARCHAR(64),           -- Single-use approval token
    COMPLETED_AT   TIMESTAMP,
    ERROR_MSG      VARCHAR(500)
);

-- Audit log (hash-chained, insert-only)
CREATE TABLE AUDIT_LOG (
    ID             INT NOT NULL PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    ACTOR          VARCHAR(100) NOT NULL,
    ACTION         VARCHAR(50) NOT NULL,
    SUBJECT        INT,                   -- Subject ID if applicable
    DETAIL         CLOB NOT NULL,         -- JSON detail (no PII values)
    PREV_HASH      VARCHAR(64) NOT NULL,
    HASH           VARCHAR(64) NOT NULL,
    CREATED_AT     TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP
);

-- Insert genesis audit row
INSERT INTO AUDIT_LOG (ACTOR, ACTION, SUBJECT, DETAIL, PREV_HASH, HASH)
SELECT 'SYSTEM', 'GENESIS', NULL, '{"event":"audit_log_initialized"}',
       'GENESIS', 'GENESIS'
FROM SYSIBM.SYSDUMMY1
WHERE NOT EXISTS (
    SELECT 1 FROM AUDIT_LOG WHERE ACTION = 'GENESIS'
);

-- Create indexes
CREATE INDEX IDX_PII_MAP_LABEL ON PII_MAP(LABEL);
CREATE INDEX IDX_REQUESTS_STATUS ON REQUESTS(STATUS);
CREATE INDEX IDX_REQUESTS_DUE ON REQUESTS(DUE_AT);
CREATE INDEX IDX_REQUESTS_SUBJECT ON REQUESTS(SUBJECT_ID);
CREATE INDEX IDX_AUDIT_ACTOR ON AUDIT_LOG(ACTOR);
CREATE INDEX IDX_AUDIT_ACTION ON AUDIT_LOG(ACTION);
CREATE INDEX IDX_AUDIT_CREATED ON AUDIT_LOG(CREATED_AT);

-- Insert initial retention rules
MERGE INTO RETENTION_RULES AS target
USING (
    VALUES
        ('PATIENT',        'ANONYMISE', 'Keep referenced records; remove patient identifiers',
         'Retention policy required by dependent BILLING records', 'N'),
        ('APPOINTMENT',    'ANONYMISE', 'Keep referenced records; remove personal and health data',
         'Retention policy required by dependent BILLING records', 'N'),
        ('PRESCRIPTION',   'ERASE',     'Prescription records contain health data',
         'DPDP Act Section 13 (verify against Act text)', 'N'),
        ('LAB_REPORT',     'ERASE',     'Lab reports contain health data',
         'DPDP Act Section 13 (verify against Act text)', 'N'),
        ('BILLING',        'RETAIN',    'Financial records required for tax compliance',
         'Income Tax Act, verify retention period under tax law', 'N'),
        ('SUPPORT_TICKET', 'ANONYMISE', 'Keep ticket statistics, remove identifiers',
         'Internal policy - balance service quality with privacy', 'N'),
        ('MARKETING_LIST', 'ERASE',     'Marketing consent withdrawn',
         'DPDP Act consent withdrawal provisions (verify)', 'N')
) AS source (TABNAME, ACTION, REASON, SOURCE, VERIFIED)
ON target.TABNAME = source.TABNAME
WHEN NOT MATCHED THEN
    INSERT (TABNAME, ACTION, REASON, SOURCE, VERIFIED)
    VALUES (source.TABNAME, source.ACTION, source.REASON, source.SOURCE, source.VERIFIED);
