-- Synthetic clinic database schema with deliberately awkward PII placement
-- This schema is designed to test the classifier with realistic challenges

-- Patient master table (root entity)
CREATE TABLE PATIENT (
    ID             INT NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    FULL_NM        VARCHAR(100),          -- full name (PII)
    CUST_MAIL_ID   VARCHAR(100),          -- email in ugly name (PII)
    PH_NO          BIGINT,                -- phone as number, not string (PII)
    DOB_DT         DATE,                  -- date of birth (PII)
    GOVT_ID        VARCHAR(20),           -- could be PAN or Aadhaar (PII)
    ADDR1          VARCHAR(200),          -- address line 1 (PII)
    ADDR2          VARCHAR(200),          -- address line 2 (PII)
    CITY_NM        VARCHAR(50),           -- city (potentially PII)
    PINCODE        VARCHAR(10),           -- postal code (potentially PII)
    REGISTRATION_DT TIMESTAMP DEFAULT CURRENT TIMESTAMP,
    NOTES          CLOB                   -- free text that may hide PII
);

-- Appointments
CREATE TABLE APPOINTMENT (
    ID             INT NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    PATIENT_ID     INT NOT NULL,
    APPT_DT        DATE NOT NULL,
    APPT_TIME      TIME NOT NULL,
    DOCTOR_NM      VARCHAR(100),          -- doctor name (potentially PII depending on policy)
    REASON         VARCHAR(500),          -- chief complaint (health data, PII)
    STATUS         VARCHAR(20) DEFAULT 'SCHEDULED',
    NOTES          VARCHAR(1000),
    FOREIGN KEY (PATIENT_ID) REFERENCES PATIENT(ID)
);

-- Billing records (retention required for tax purposes)
CREATE TABLE BILLING (
    ID             INT NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    PATIENT_ID     INT NOT NULL,
    APPT_ID        INT,
    BILL_DT        DATE NOT NULL,
    AMOUNT         DECIMAL(10,2) NOT NULL,
    TAX_AMT        DECIMAL(10,2),
    PAYMENT_MODE   VARCHAR(20),
    INVOICE_NO     VARCHAR(30) NOT NULL UNIQUE,  -- not PII
    FISCAL_YEAR    VARCHAR(10),
    FOREIGN KEY (PATIENT_ID) REFERENCES PATIENT(ID),
    FOREIGN KEY (APPT_ID) REFERENCES APPOINTMENT(ID)
);

-- Prescriptions (health data)
CREATE TABLE PRESCRIPTION (
    ID             INT NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    PATIENT_ID     INT NOT NULL,
    APPT_ID        INT,
    PRESCRIBED_DT  DATE NOT NULL,
    MEDICATION     VARCHAR(200) NOT NULL,
    DOSAGE         VARCHAR(100),
    DURATION_DAYS  INT,
    INSTRUCTIONS   VARCHAR(500),          -- may contain health info (PII)
    FOREIGN KEY (PATIENT_ID) REFERENCES PATIENT(ID),
    FOREIGN KEY (APPT_ID) REFERENCES APPOINTMENT(ID)
);

-- Lab reports (health data)
CREATE TABLE LAB_REPORT (
    ID             INT NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    PATIENT_ID     INT NOT NULL,
    APPT_ID        INT,
    TEST_NM        VARCHAR(100) NOT NULL,
    TEST_DT        DATE NOT NULL,
    RESULT_VALUE   VARCHAR(200),          -- may contain health data (PII)
    NORMAL_RANGE   VARCHAR(100),
    UNIT           VARCHAR(20),
    REMARKS        VARCHAR(500),          -- may contain health info (PII)
    FOREIGN KEY (PATIENT_ID) REFERENCES PATIENT(ID),
    FOREIGN KEY (APPT_ID) REFERENCES APPOINTMENT(ID)
);

-- Support tickets
CREATE TABLE SUPPORT_TICKET (
    ID             INT NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    PATIENT_ID     INT,
    TICKET_REF_NO  VARCHAR(20) NOT NULL UNIQUE,  -- looks like PII but isn't (10 digits)
    SUBJECT        VARCHAR(200),
    DESCRIPTION    CLOB,                  -- may contain PII in free text
    STATUS         VARCHAR(20) DEFAULT 'OPEN',
    CREATED_DT     TIMESTAMP DEFAULT CURRENT TIMESTAMP,
    RESOLVED_DT    TIMESTAMP,
    FOREIGN KEY (PATIENT_ID) REFERENCES PATIENT(ID)
);

-- Marketing list (erasable when consent withdrawn)
CREATE TABLE MARKETING_LIST (
    ID             INT NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    PATIENT_ID     INT NOT NULL,
    CAMPAIGN_NM    VARCHAR(100),
    ADDED_DT       DATE NOT NULL,
    EMAIL_ADDR     VARCHAR(100),          -- email (PII)
    PHONE_NUM      VARCHAR(20),           -- phone (PII)
    CONSENT_STATUS VARCHAR(20) DEFAULT 'GRANTED',
    FOREIGN KEY (PATIENT_ID) REFERENCES PATIENT(ID)
);

-- Create indexes for performance
CREATE INDEX IDX_APPT_PATIENT ON APPOINTMENT(PATIENT_ID);
CREATE INDEX IDX_BILL_PATIENT ON BILLING(PATIENT_ID);
CREATE INDEX IDX_PRESC_PATIENT ON PRESCRIPTION(PATIENT_ID);
CREATE INDEX IDX_LAB_PATIENT ON LAB_REPORT(PATIENT_ID);
CREATE INDEX IDX_TICKET_PATIENT ON SUPPORT_TICKET(PATIENT_ID);
CREATE INDEX IDX_MARKETING_PATIENT ON MARKETING_LIST(PATIENT_ID);