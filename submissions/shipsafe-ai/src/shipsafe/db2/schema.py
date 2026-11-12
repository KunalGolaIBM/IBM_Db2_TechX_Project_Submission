"""IBM Db2 schema for ShipSafe: tables, indexes, views and SQL PL stored procedures.

Everything here runs against IBM Db2 12.1+. Vector tables used by LangChain
(`POLICY_VECTORS`) and Haystack (`MEMORY_VECTORS`) are created by those
libraries in the same schema.
"""

# Tables are created inside the schema named by DB2_SCHEMA (default SHIPSAFE).
# Order matters: parents before children so foreign keys resolve.
DB2_TABLES = {
    "PROJECTS": """
        CREATE TABLE PROJECTS (
            PROJECT_ID      VARCHAR(96)  NOT NULL PRIMARY KEY,
            REPO_ROOT_HASH  VARCHAR(64)  NOT NULL,
            NAME            VARCHAR(128) NOT NULL,
            DEFAULT_BRANCH  VARCHAR(64)  DEFAULT 'main',
            CREATED_AT      BIGINT       NOT NULL
        )""",
    "ASSESSMENTS": """
        CREATE TABLE ASSESSMENTS (
            ASSESSMENT_ID   VARCHAR(64)  NOT NULL PRIMARY KEY,
            PROJECT_ID      VARCHAR(96)  NOT NULL,
            COMMIT_SHA      VARCHAR(40),
            BASE_SHA        VARCHAR(40),
            PROFILE         VARCHAR(32)  NOT NULL,
            STATUS          VARCHAR(32)  NOT NULL,
            GATE_REASON     VARCHAR(512),
            STARTED_AT      BIGINT       NOT NULL,
            FINISHED_AT     BIGINT       NOT NULL,
            FINDINGS_COUNT  INTEGER      DEFAULT 0,
            CRITICAL_COUNT  INTEGER      DEFAULT 0,
            HIGH_COUNT      INTEGER      DEFAULT 0,
            MEDIUM_COUNT    INTEGER      DEFAULT 0,
            LOW_COUNT       INTEGER      DEFAULT 0,
            CONSTRAINT FK_ASM_PROJ FOREIGN KEY (PROJECT_ID)
                REFERENCES PROJECTS(PROJECT_ID) ON DELETE CASCADE
        )""",
    "TOOL_RUNS": """
        CREATE TABLE TOOL_RUNS (
            TOOL_RUN_ID     VARCHAR(96)  NOT NULL PRIMARY KEY,
            ASSESSMENT_ID   VARCHAR(64)  NOT NULL,
            TOOL_NAME       VARCHAR(64)  NOT NULL,
            VERSION         VARCHAR(64),
            EXIT_CODE       INTEGER      NOT NULL,
            DURATION_MS     INTEGER      NOT NULL,
            STATUS          VARCHAR(32)  NOT NULL,
            MESSAGE         VARCHAR(1024),
            CONSTRAINT FK_RUN_ASM FOREIGN KEY (ASSESSMENT_ID)
                REFERENCES ASSESSMENTS(ASSESSMENT_ID) ON DELETE CASCADE
        )""",
    "FINDINGS": """
        CREATE TABLE FINDINGS (
            FINDING_ID      VARCHAR(96)  NOT NULL PRIMARY KEY,
            ASSESSMENT_ID   VARCHAR(64)  NOT NULL,
            FINGERPRINT     CHAR(64)     NOT NULL,
            SOURCE_TOOL     VARCHAR(64)  NOT NULL,
            RULE_ID         VARCHAR(64)  NOT NULL,
            CATEGORY        VARCHAR(32)  NOT NULL,
            SEVERITY        VARCHAR(16)  NOT NULL,
            CONFIDENCE      VARCHAR(16)  NOT NULL,
            FILE_PATH       VARCHAR(512),
            LINE_START      INTEGER,
            LINE_END        INTEGER,
            TITLE           VARCHAR(256) NOT NULL,
            DESCRIPTION     VARCHAR(2048),
            EVIDENCE_JSON   CLOB(1M),
            REMEDIATION     VARCHAR(2048),
            STATUS          VARCHAR(32)  DEFAULT 'new',
            REFERENCES_JSON CLOB(64K),
            CONSTRAINT FK_FND_ASM FOREIGN KEY (ASSESSMENT_ID)
                REFERENCES ASSESSMENTS(ASSESSMENT_ID) ON DELETE CASCADE
        )""",
    "DEPENDENCIES": """
        CREATE TABLE DEPENDENCIES (
            DEPENDENCY_ID   VARCHAR(96)  NOT NULL PRIMARY KEY,
            PROJECT_ID      VARCHAR(96)  NOT NULL,
            PACKAGE_NAME    VARCHAR(128) NOT NULL,
            VERSION         VARCHAR(64)  NOT NULL,
            MANIFEST_PATH   VARCHAR(512),
            ECOSYSTEM       VARCHAR(32)  NOT NULL,
            CONSTRAINT FK_DEP_PROJ FOREIGN KEY (PROJECT_ID)
                REFERENCES PROJECTS(PROJECT_ID) ON DELETE CASCADE
        )""",
    "KNOWLEDGE_DOCS": """
        CREATE TABLE KNOWLEDGE_DOCS (
            DOC_ID          VARCHAR(64)  NOT NULL PRIMARY KEY,
            TITLE           VARCHAR(256) NOT NULL,
            SOURCE          VARCHAR(256) NOT NULL,
            CATEGORY        VARCHAR(64)  NOT NULL,
            VERSION         VARCHAR(16)  NOT NULL,
            CONTENT         CLOB(1M)     NOT NULL,
            CHUNK_COUNT     INTEGER      DEFAULT 0,
            INGESTED_AT     BIGINT       NOT NULL
        )""",
    "ASSESSMENT_DIFFS": """
        CREATE TABLE ASSESSMENT_DIFFS (
            DIFF_ID             VARCHAR(160) NOT NULL PRIMARY KEY,
            CURRENT_ID          VARCHAR(64)  NOT NULL,
            PREVIOUS_ID         VARCHAR(64)  NOT NULL,
            FINDING_FINGERPRINT CHAR(64)     NOT NULL,
            CHANGE_TYPE         VARCHAR(16)  NOT NULL,
            TITLE               VARCHAR(256),
            SEVERITY            VARCHAR(16),
            CONSTRAINT FK_DIFF_CUR FOREIGN KEY (CURRENT_ID)
                REFERENCES ASSESSMENTS(ASSESSMENT_ID) ON DELETE CASCADE
        )""",
    "API_TOKENS": """
        CREATE TABLE API_TOKENS (
            TOKEN_ID        VARCHAR(32)  NOT NULL PRIMARY KEY,
            NAME            VARCHAR(64)  NOT NULL,
            ROLE            VARCHAR(16)  NOT NULL,
            TOKEN_HASH      CHAR(64)     NOT NULL,
            CREATED_AT      BIGINT       NOT NULL,
            LAST_USED_AT    BIGINT,
            REVOKED         SMALLINT     NOT NULL DEFAULT 0,
            CONSTRAINT UQ_TOKEN_HASH UNIQUE (TOKEN_HASH),
            CONSTRAINT CK_TOKEN_ROLE CHECK (ROLE IN ('viewer', 'operator', 'admin'))
        )""",
    "AUDIT_LOG": """
        CREATE TABLE AUDIT_LOG (
            EVENT_ID        VARCHAR(40)  NOT NULL PRIMARY KEY,
            TS              BIGINT       NOT NULL,
            ACTOR           VARCHAR(64)  NOT NULL,
            ROLE            VARCHAR(16),
            ACTION          VARCHAR(64)  NOT NULL,
            TARGET          VARCHAR(512),
            OUTCOME         VARCHAR(16)  NOT NULL,
            DETAIL          VARCHAR(1024),
            CLIENT_IP       VARCHAR(64)
        )""",
    # One row per IDE guard check (code checked by Bob / VS Code / Claude before it is written).
    "GUARD_EVENTS": """
        CREATE TABLE GUARD_EVENTS (
            EVENT_ID        VARCHAR(40)  NOT NULL PRIMARY KEY,
            TS              BIGINT       NOT NULL,
            CLIENT          VARCHAR(32)  NOT NULL,
            TOOL            VARCHAR(48)  NOT NULL,
            PROJECT         VARCHAR(128),
            FILE_PATH       VARCHAR(512),
            LANGUAGE        VARCHAR(24),
            FINDINGS_COUNT  INTEGER      NOT NULL DEFAULT 0,
            MAX_SEVERITY    VARCHAR(16),
            RULE_IDS        VARCHAR(1024),
            VERDICT         VARCHAR(16)  NOT NULL,
            DURATION_MS     INTEGER      NOT NULL,
            CONSTRAINT CK_GUARD_VERDICT CHECK (VERDICT IN ('clean', 'warn', 'block'))
        )""",
    # One row per fix attempt by the CrewAI fix-and-verify crew.
    "FIX_ATTEMPTS": """
        CREATE TABLE FIX_ATTEMPTS (
            FIX_ID          VARCHAR(40)  NOT NULL PRIMARY KEY,
            TS              BIGINT       NOT NULL,
            FILE_PATH       VARCHAR(512),
            LANGUAGE        VARCHAR(24),
            MODEL           VARCHAR(96)  NOT NULL,
            ITERATIONS      SMALLINT     NOT NULL,
            VERIFIED        SMALLINT     NOT NULL,
            ISSUES_BEFORE   INTEGER      NOT NULL,
            ISSUES_AFTER    INTEGER      NOT NULL,
            RULE_IDS        VARCHAR(1024),
            DURATION_MS     INTEGER      NOT NULL,
            PATCH           CLOB(1M),
            CONSTRAINT CK_FIX_VERIFIED CHECK (VERIFIED IN (0, 1))
        )""",
}

DB2_INDEXES = {
    "IDX_ASM_PROJ_TIME": "CREATE INDEX IDX_ASM_PROJ_TIME ON ASSESSMENTS(PROJECT_ID, STARTED_AT DESC)",
    "IDX_FND_ASM_SEV": "CREATE INDEX IDX_FND_ASM_SEV ON FINDINGS(ASSESSMENT_ID, SEVERITY)",
    "IDX_FND_FP": "CREATE INDEX IDX_FND_FP ON FINDINGS(FINGERPRINT)",
    "IDX_RUN_ASM": "CREATE INDEX IDX_RUN_ASM ON TOOL_RUNS(ASSESSMENT_ID)",
    "IDX_DEP_PKG": "CREATE INDEX IDX_DEP_PKG ON DEPENDENCIES(PACKAGE_NAME, VERSION)",
    "IDX_AUDIT_TS": "CREATE INDEX IDX_AUDIT_TS ON AUDIT_LOG(TS DESC)",
    "IDX_AUDIT_ACTOR": "CREATE INDEX IDX_AUDIT_ACTOR ON AUDIT_LOG(ACTOR, TS DESC)",
    "IDX_GUARD_TS": "CREATE INDEX IDX_GUARD_TS ON GUARD_EVENTS(TS DESC)",
    "IDX_GUARD_PROJ": "CREATE INDEX IDX_GUARD_PROJ ON GUARD_EVENTS(PROJECT, TS DESC)",
    "IDX_FIX_TS": "CREATE INDEX IDX_FIX_TS ON FIX_ATTEMPTS(TS DESC)",
}

# Risk trend per project: Db2 OLAP window functions compute the delta between
# consecutive assessments directly in the database.
DB2_VIEWS = {
    "V_RISK_TREND": """
        CREATE OR REPLACE VIEW V_RISK_TREND AS
        SELECT A.PROJECT_ID,
               P.NAME AS PROJECT_NAME,
               A.ASSESSMENT_ID,
               A.STATUS,
               A.STARTED_AT,
               A.CRITICAL_COUNT,
               A.HIGH_COUNT,
               A.MEDIUM_COUNT,
               A.LOW_COUNT,
               (A.CRITICAL_COUNT * 10 + A.HIGH_COUNT * 5 + A.MEDIUM_COUNT * 2 + A.LOW_COUNT) AS RISK_SCORE,
               (A.CRITICAL_COUNT * 10 + A.HIGH_COUNT * 5 + A.MEDIUM_COUNT * 2 + A.LOW_COUNT)
                 - LAG(A.CRITICAL_COUNT * 10 + A.HIGH_COUNT * 5 + A.MEDIUM_COUNT * 2 + A.LOW_COUNT)
                   OVER (PARTITION BY A.PROJECT_ID ORDER BY A.STARTED_AT) AS RISK_DELTA,
               ROW_NUMBER() OVER (PARTITION BY A.PROJECT_ID ORDER BY A.STARTED_AT DESC) AS RECENCY_RANK
        FROM ASSESSMENTS A
        JOIN PROJECTS P ON P.PROJECT_ID = A.PROJECT_ID""",
    # Open risk per project: latest assessment per project only (ROW_NUMBER filter).
    "V_PROJECT_POSTURE": """
        CREATE OR REPLACE VIEW V_PROJECT_POSTURE AS
        SELECT PROJECT_ID, PROJECT_NAME, ASSESSMENT_ID, STATUS, STARTED_AT,
               CRITICAL_COUNT, HIGH_COUNT, MEDIUM_COUNT, LOW_COUNT, RISK_SCORE, RISK_DELTA
        FROM V_RISK_TREND
        WHERE RECENCY_RANK = 1""",
}

# Name of the langchain-db2 (DB2VS) table holding policy chunk embeddings.
VECTOR_TABLE = "POLICY_VECTORS"


# SQL PL stored procedures. Business rules that belong next to the data run in Db2.
DB2_PROCEDURES = {
    # Risk score, delta against the previous run and a trend label for one project.
    "SP_PROJECT_RISK": """
        CREATE OR REPLACE PROCEDURE SP_PROJECT_RISK (
            IN  P_PROJECT_ID VARCHAR(96),
            OUT P_RISK_SCORE INTEGER,
            OUT P_RISK_DELTA INTEGER,
            OUT P_TREND      VARCHAR(16),
            OUT P_RUNS       INTEGER)
        LANGUAGE SQL
        READS SQL DATA
        BEGIN
            DECLARE V_PREV INTEGER DEFAULT NULL;
            -- OUT values are never NULL so every client driver can bind them;
            -- P_TREND says whether a delta exists ('unknown' = no runs, 'new' = one run).
            SET P_RISK_SCORE = 0;
            SET P_RISK_DELTA = 0;
            SELECT COUNT(*) INTO P_RUNS FROM ASSESSMENTS WHERE PROJECT_ID = P_PROJECT_ID;
            IF P_RUNS = 0 THEN
                SET P_TREND = 'unknown';
            ELSE
                SELECT RISK_SCORE INTO P_RISK_SCORE FROM V_RISK_TREND
                 WHERE PROJECT_ID = P_PROJECT_ID AND RECENCY_RANK = 1;
                IF P_RUNS > 1 THEN
                    SELECT RISK_SCORE INTO V_PREV FROM V_RISK_TREND
                     WHERE PROJECT_ID = P_PROJECT_ID AND RECENCY_RANK = 2;
                    SET P_RISK_DELTA = P_RISK_SCORE - V_PREV;
                END IF;
                SET P_TREND = CASE
                    WHEN V_PREV IS NULL THEN 'new'
                    WHEN P_RISK_DELTA < 0 THEN 'improving'
                    WHEN P_RISK_DELTA > 0 THEN 'worsening'
                    ELSE 'steady' END;
            END IF;
        END""",
    # Retention: delete assessments (cascades to findings, tool runs, diffs) and IDE events older than N days.
    "SP_PURGE_HISTORY": """
        CREATE OR REPLACE PROCEDURE SP_PURGE_HISTORY (
            IN  P_KEEP_DAYS INTEGER,
            OUT P_ASSESSMENTS_DELETED INTEGER,
            OUT P_EVENTS_DELETED INTEGER)
        LANGUAGE SQL
        MODIFIES SQL DATA
        BEGIN
            DECLARE V_CUTOFF BIGINT;
            IF P_KEEP_DAYS < 1 THEN
                SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'P_KEEP_DAYS must be at least 1';
            END IF;
            SET V_CUTOFF = (BIGINT(DAYS(CURRENT TIMESTAMP - CURRENT TIMEZONE)) - 719163 - P_KEEP_DAYS) * 86400000
                           + BIGINT(MIDNIGHT_SECONDS(CURRENT TIMESTAMP - CURRENT TIMEZONE)) * 1000;
            DELETE FROM ASSESSMENTS WHERE FINISHED_AT < V_CUTOFF;
            GET DIAGNOSTICS P_ASSESSMENTS_DELETED = ROW_COUNT;
            DELETE FROM GUARD_EVENTS WHERE TS < V_CUTOFF;
            GET DIAGNOSTICS P_EVENTS_DELETED = ROW_COUNT;
            DELETE FROM FIX_ATTEMPTS WHERE TS < V_CUTOFF;
        END""",
    # What ShipSafe caught inside the IDE since a point in time, as a result set.
    "SP_GUARD_SUMMARY": """
        CREATE OR REPLACE PROCEDURE SP_GUARD_SUMMARY (IN P_SINCE BIGINT)
        LANGUAGE SQL
        READS SQL DATA
        DYNAMIC RESULT SETS 1
        BEGIN
            DECLARE C1 CURSOR WITH RETURN TO CALLER FOR
                SELECT CLIENT,
                       COUNT(*)                                             AS CHECKS,
                       SUM(CASE WHEN VERDICT = 'block' THEN 1 ELSE 0 END)   AS BLOCKED,
                       SUM(CASE WHEN VERDICT = 'warn'  THEN 1 ELSE 0 END)   AS WARNED,
                       SUM(FINDINGS_COUNT)                                  AS ISSUES_CAUGHT,
                       (SELECT COUNT(*) FROM FIX_ATTEMPTS F
                         WHERE F.TS >= P_SINCE AND F.VERIFIED = 1)          AS VERIFIED_FIXES
                  FROM GUARD_EVENTS
                 WHERE TS >= P_SINCE
                 GROUP BY CLIENT
                 ORDER BY CHECKS DESC;
            OPEN C1;
        END""",
}
