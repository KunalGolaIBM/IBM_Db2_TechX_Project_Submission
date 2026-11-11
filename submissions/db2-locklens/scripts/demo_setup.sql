-- LockLens demo: creates a dedicated, disposable schema and table. Touches nothing else.
-- Run once, as a user allowed to create schemas:  db2 -tvf demo_setup.sql
CREATE SCHEMA LOCKLENS_DEMO;

CREATE TABLE LOCKLENS_DEMO.ACCOUNTS (
    ID      INTEGER       NOT NULL PRIMARY KEY,
    OWNER   VARCHAR(40)   NOT NULL,
    BALANCE DECIMAL(12,2) NOT NULL
);

INSERT INTO LOCKLENS_DEMO.ACCOUNTS (ID, OWNER, BALANCE) VALUES
    (1, 'Alice', 1000.00),
    (2, 'Bob',    500.00),
    (3, 'Carol',  750.00);

COMMIT;
SELECT * FROM LOCKLENS_DEMO.ACCOUNTS ORDER BY ID;
