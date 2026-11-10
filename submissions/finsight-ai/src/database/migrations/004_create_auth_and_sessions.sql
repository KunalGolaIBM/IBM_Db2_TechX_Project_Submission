-- ==============================================================================
-- Migration: 004_create_auth_and_sessions.sql
-- Description: Adds authentication attributes to FINSIGHT.USERS and creates
--              FINSIGHT.USER_SESSIONS for secure, hashed session management.
-- ==============================================================================

-- 1. Alter USERS table to support password authentication
ALTER TABLE FINSIGHT.USERS ADD COLUMN password_hash VARCHAR(255);
ALTER TABLE FINSIGHT.USERS ADD COLUMN is_active SMALLINT NOT NULL DEFAULT 1;
ALTER TABLE FINSIGHT.USERS ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP;

CALL SYSPROC.ADMIN_CMD('REORG TABLE FINSIGHT.USERS');

-- 2. Create USER_SESSIONS table
CREATE TABLE FINSIGHT.USER_SESSIONS (
    session_token_hash VARCHAR(64) NOT NULL PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    csrf_token_hash VARCHAR(64) NOT NULL,
    user_agent VARCHAR(255),
    ip_address VARCHAR(45),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_active_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT FK_SESSION_USER FOREIGN KEY (user_id) REFERENCES FINSIGHT.USERS(user_id) ON DELETE CASCADE
);

CREATE INDEX FINSIGHT.IDX_SESSION_EXPIRES ON FINSIGHT.USER_SESSIONS (expires_at);
CREATE INDEX FINSIGHT.IDX_SESSION_USER ON FINSIGHT.USER_SESSIONS (user_id);
