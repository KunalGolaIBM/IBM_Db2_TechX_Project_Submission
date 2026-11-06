-- Custodian schema. Run by src/seed.py as the instance owner (db2inst1, SYSADM/SECADM).
-- BANK      = the fictional fintech's data (what the agent touches)
-- CUSTODIAN = the control plane (policy, approvals, ledger); end users have NO grants on it.

------------------------------------------------------------------------------------------
-- 1. Business tables. CUSTOMERS and ACCOUNTS are system-period temporal tables:
--    Db2 itself copies every old row version into *_HIST on UPDATE/DELETE.
------------------------------------------------------------------------------------------
CREATE TABLE BANK.CUSTOMERS (
  CUSTOMER_ID  INTEGER      NOT NULL PRIMARY KEY,
  FULL_NAME    VARCHAR(80)  NOT NULL,
  EMAIL        VARCHAR(120) NOT NULL,
  PAN          CHAR(10)     NOT NULL,          -- Indian tax ID (fake)
  CARD_NUMBER  CHAR(19)     NOT NULL,          -- 4000-xxxx-xxxx-xxxx (fake test range)
  SEGMENT      VARCHAR(10)  NOT NULL,          -- RETAIL | PRIVATE
  STATUS       VARCHAR(10)  NOT NULL,          -- ACTIVE | INACTIVE
  LAST_LOGIN   DATE,
  SYS_START    TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW BEGIN IMPLICITLY HIDDEN,
  SYS_END      TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW END IMPLICITLY HIDDEN,
  TRANS_ID      TIMESTAMP(12) GENERATED ALWAYS AS TRANSACTION START ID IMPLICITLY HIDDEN,
  PERIOD SYSTEM_TIME (SYS_START, SYS_END)
);
CREATE TABLE BANK.CUSTOMERS_HIST LIKE BANK.CUSTOMERS;
ALTER TABLE BANK.CUSTOMERS ADD VERSIONING USE HISTORY TABLE BANK.CUSTOMERS_HIST;

CREATE TABLE BANK.ACCOUNTS (
  ACCOUNT_ID     INTEGER       NOT NULL PRIMARY KEY,
  CUSTOMER_ID    INTEGER       NOT NULL,
  PRODUCT        VARCHAR(20)   NOT NULL,       -- CREDIT_CARD | SAVINGS | LOAN
  BALANCE        DECIMAL(12,2) NOT NULL,
  LATE_FEE       DECIMAL(8,2)  NOT NULL,
  INTEREST_RATE  DECIMAL(5,2)  NOT NULL,
  SYS_START      TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW BEGIN IMPLICITLY HIDDEN,
  SYS_END        TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW END IMPLICITLY HIDDEN,
  TRANS_ID        TIMESTAMP(12) GENERATED ALWAYS AS TRANSACTION START ID IMPLICITLY HIDDEN,
  PERIOD SYSTEM_TIME (SYS_START, SYS_END)
);
CREATE TABLE BANK.ACCOUNTS_HIST LIKE BANK.ACCOUNTS;
ALTER TABLE BANK.ACCOUNTS ADD VERSIONING USE HISTORY TABLE BANK.ACCOUNTS_HIST;
CREATE INDEX BANK.ACCOUNTS_CUST ON BANK.ACCOUNTS (CUSTOMER_ID);

CREATE TABLE BANK.TICKETS (
  TICKET_ID    INTEGER       NOT NULL PRIMARY KEY,
  CUSTOMER_ID  INTEGER       NOT NULL,
  SUBJECT      VARCHAR(200)  NOT NULL,
  BODY         VARCHAR(2000) NOT NULL,
  STATUS       VARCHAR(10)   NOT NULL,         -- OPEN | CLOSED
  CREATED_AT   TIMESTAMP     NOT NULL DEFAULT CURRENT TIMESTAMP
);
-- BANK.TICKET_EMBEDDINGS (VECTOR(384, FLOAT32)) is created by langchain-db2 DB2VS in seed.py.

------------------------------------------------------------------------------------------
-- 2. Identities. PRIYA / ARJUN are OS users in the container; roles carry the privileges.
------------------------------------------------------------------------------------------
CREATE ROLE SUPPORT;
CREATE ROLE ADMINS;
GRANT ROLE SUPPORT TO USER PRIYA;
GRANT ROLE ADMINS TO USER ARJUN;
GRANT CONNECT ON DATABASE TO ROLE SUPPORT;
GRANT CONNECT ON DATABASE TO ROLE ADMINS;
GRANT SELECT, INSERT, UPDATE, DELETE ON BANK.CUSTOMERS TO ROLE SUPPORT;
GRANT SELECT, INSERT, UPDATE, DELETE ON BANK.ACCOUNTS  TO ROLE SUPPORT;
GRANT SELECT, INSERT, UPDATE, DELETE ON BANK.TICKETS   TO ROLE SUPPORT;
GRANT SELECT, INSERT, UPDATE, DELETE ON BANK.CUSTOMERS TO ROLE ADMINS;
GRANT SELECT, INSERT, UPDATE, DELETE ON BANK.ACCOUNTS  TO ROLE ADMINS;
GRANT SELECT, INSERT, UPDATE, DELETE ON BANK.TICKETS   TO ROLE ADMINS;

------------------------------------------------------------------------------------------
-- 3. Control plane tables (only db2inst1 = the Custodian gateway can touch these).
------------------------------------------------------------------------------------------
-- Blast-radius policy: rows <= AUTO_ALLOW_MAX -> ALLOW, <= APPROVAL_MAX -> APPROVE, else DENY.
-- No matching row -> DENY. SELECTs are always allowed: RCAC decides what they can see.
CREATE TABLE CUSTODIAN.POLICY (
  ROLE_NAME       VARCHAR(30) NOT NULL,
  TABLE_NAME      VARCHAR(30) NOT NULL,
  OPERATION       VARCHAR(10) NOT NULL,
  AUTO_ALLOW_MAX  INTEGER     NOT NULL,
  APPROVAL_MAX    INTEGER     NOT NULL,
  PRIMARY KEY (ROLE_NAME, TABLE_NAME, OPERATION)
);
INSERT INTO CUSTODIAN.POLICY VALUES
  ('SUPPORT', 'TICKETS',   'UPDATE',  5,  50),
  ('SUPPORT', 'TICKETS',   'INSERT',  1,   1),
  ('SUPPORT', 'CUSTOMERS', 'UPDATE',  0,   5),
  ('SUPPORT', 'CUSTOMERS', 'DELETE',  0,  50),
  ('SUPPORT', 'ACCOUNTS',  'UPDATE',  0,   5),
  ('ADMINS',  'TICKETS',   'UPDATE', 50, 500),
  ('ADMINS',  'CUSTOMERS', 'UPDATE', 10, 200),
  ('ADMINS',  'CUSTOMERS', 'DELETE',  0, 100),
  ('ADMINS',  'ACCOUNTS',  'UPDATE', 10, 200);

-- Every statement the agent tries, with the decision, the deciding layer and the Db2
-- timestamp it ran at (AS_OF) so any answer can be replayed against the data it saw.
CREATE TABLE CUSTODIAN.LEDGER (
  ENTRY_ID        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  CREATED_AT      TIMESTAMP(12) NOT NULL DEFAULT CURRENT TIMESTAMP,
  DB_USER         VARCHAR(30)   NOT NULL,
  PROMPT          VARCHAR(2000),
  SQL_TEXT        VARCHAR(4000) NOT NULL,
  STATEMENT_TYPE  VARCHAR(10),
  TABLE_NAME      VARCHAR(30),
  DECISION        VARCHAR(10)   NOT NULL,      -- ALLOW | APPROVE | DENY | EXECUTED | ERROR
  LAYER           VARCHAR(20)   NOT NULL,      -- classifier | blast-radius | approval | rcac | db2-privileges
  REASON          VARCHAR(1000),
  ROWS_AFFECTED   INTEGER,
  TABLE_ROWS      INTEGER,
  EST_COST        DOUBLE,
  AS_OF           TIMESTAMP(12),                -- when a SELECT ran (for replay)
  TX_TS           TIMESTAMP(12),                -- the write's transaction timestamp (for rewind)
  ANSWER          VARCHAR(4000),
  REWOUND_BY      INTEGER                       -- ledger entry of the rewind, if any
);

CREATE TABLE CUSTODIAN.APPROVALS (
  APPROVAL_ID    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  LEDGER_ID      INTEGER       NOT NULL,
  REQUESTED_BY   VARCHAR(30)   NOT NULL,
  SQL_TEXT       VARCHAR(4000) NOT NULL,
  ROWS_AFFECTED  INTEGER       NOT NULL,
  THREAD_ID      VARCHAR(64),
  STATUS         VARCHAR(10)   NOT NULL DEFAULT 'PENDING',   -- PENDING | APPROVED | REJECTED
  DECIDED_BY     VARCHAR(30),
  DECIDED_AT     TIMESTAMP
);

-- EXPLAIN tables for the gateway's cost check (EXPLAIN PLAN FOR <dml> never executes it).
CALL SYSPROC.SYSINSTALLOBJECTS('EXPLAIN', 'C', CAST(NULL AS VARCHAR(128)), 'DB2INST1');
