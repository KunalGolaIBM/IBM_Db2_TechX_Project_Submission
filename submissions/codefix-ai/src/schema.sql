-- ==============================================================================
-- CodeFix AI — IBM Db2 Schema Definition
-- ==============================================================================
-- Table: CODEFIX_HISTORY
-- Stores prompt instructions, input code, error traces, AI generated output,
-- structured explanations, and model metadata per session.
-- ==============================================================================

CREATE TABLE CODEFIX_HISTORY (
    ID VARCHAR(36) NOT NULL PRIMARY KEY,
    SESSION_ID VARCHAR(64) NOT NULL,
    LANGUAGE VARCHAR(32) NOT NULL,
    MODE VARCHAR(32) NOT NULL,
    USER_PROMPT CLOB(1048576),
    ORIGINAL_CODE CLOB(1048576),
    ERROR_MESSAGE CLOB(1048576),
    GENERATED_CODE CLOB(1048576),
    EXPLANATION CLOB(1048576),
    MODEL_NAME VARCHAR(64) NOT NULL,
    CREATED_AT TIMESTAMP DEFAULT CURRENT TIMESTAMP
);

-- Index to optimize querying history by user session and sorting chronologically
CREATE INDEX IDX_CODEFIX_SESSION ON CODEFIX_HISTORY (SESSION_ID, CREATED_AT DESC);

