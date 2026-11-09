-- =============================================================================
-- Migration: 001_initial_schema.sql
-- Product: Cloud Loop - AI Opportunity Intelligence Platform
-- Target: IBM Db2 (Compatible with Db2 on Cloud & Db2 Community Edition)
-- =============================================================================

-- 1. Table: OPPORTUNITIES
-- Stores all unified student programs, jobs, internships, hackathons, and certifications
CREATE TABLE OPPORTUNITIES (
    ID                  VARCHAR(64)     NOT NULL PRIMARY KEY,
    SLUG                VARCHAR(128)    NOT NULL,
    TITLE               VARCHAR(255)    NOT NULL,
    ORGANIZATION        VARCHAR(128)    NOT NULL,
    OPPORTUNITY_TYPE    VARCHAR(64)     NOT NULL, -- 'program', 'internship', 'job', 'event', 'certification'
    CATEGORY            VARCHAR(64)     NOT NULL, -- 'Software', 'AI/ML', 'Cloud', 'Open Source', etc.
    DESCRIPTION         CLOB(64K),
    LOCATION            VARCHAR(128),
    LOCATION_TYPE       VARCHAR(32),              -- 'remote', 'onsite', 'hybrid'
    SKILLS              VARCHAR(1024),            -- JSON array or comma-separated tags
    ELIGIBILITY         VARCHAR(512),             -- Academic / graduation / degree requirements
    DEADLINE            VARCHAR(64),
    APPLICATION_URL     VARCHAR(1024)   NOT NULL,
    SOURCE_NAME         VARCHAR(64)     DEFAULT 'CloudLoop Scraper',
    SOURCE_URL          VARCHAR(1024),
    VERIFICATION_STATUS VARCHAR(32)     DEFAULT 'verified',
    FETCHED_AT          TIMESTAMP       DEFAULT CURRENT TIMESTAMP,
    CREATED_AT          TIMESTAMP       DEFAULT CURRENT TIMESTAMP,
    UPDATED_AT          TIMESTAMP       DEFAULT CURRENT TIMESTAMP
);

CREATE UNIQUE INDEX IDX_OPP_SLUG ON OPPORTUNITIES(SLUG);
CREATE INDEX IDX_OPP_TYPE ON OPPORTUNITIES(OPPORTUNITY_TYPE);
CREATE INDEX IDX_OPP_CATEGORY ON OPPORTUNITIES(CATEGORY);
CREATE INDEX IDX_OPP_DEADLINE ON OPPORTUNITIES(DEADLINE);

-- 2. Table: STUDENT_PROFILES
-- Stores verified student academic criteria and domain preferences for eligibility matching
CREATE TABLE STUDENT_PROFILES (
    USER_ID             VARCHAR(128)    NOT NULL PRIMARY KEY,
    EDUCATION           VARCHAR(128),
    DEGREE              VARCHAR(128),             -- 'B.Tech', 'B.E.', 'BCA', 'MCA', etc.
    STUDY_YEAR          INT             DEFAULT 1, -- 1st, 2nd, 3rd, 4th year
    GRADUATION_BATCH    VARCHAR(16),              -- '2025', '2026', '2027', '2028'
    SKILLS              VARCHAR(1024),            -- JSON array of verified skills
    INTERESTS           VARCHAR(1024),            -- Career aspirations & topics
    PREFERRED_DOMAINS   VARCHAR(512),             -- E.g. Cloud, Full Stack, AI/ML
    PREFERRED_LOCATIONS VARCHAR(512),             -- E.g. Remote, Bangalore, Hyderabad
    UPDATED_AT          TIMESTAMP       DEFAULT CURRENT TIMESTAMP
);

-- 3. Table: USER_OPPORTUNITY_TRACKING
-- Tracks individual application pipeline status and bookmarks
CREATE TABLE USER_OPPORTUNITY_TRACKING (
    USER_ID             VARCHAR(128)    NOT NULL,
    OPPORTUNITY_ID      VARCHAR(64)     NOT NULL,
    APPLICATION_STATUS  VARCHAR(32)     DEFAULT 'saved', -- 'saved', 'applied', 'under_review', 'not_interested'
    BOOKMARKED          SMALLINT        DEFAULT 1,
    UPDATED_AT          TIMESTAMP       DEFAULT CURRENT TIMESTAMP,
    PRIMARY KEY (USER_ID, OPPORTUNITY_ID),
    CONSTRAINT FK_TRACK_OPP FOREIGN KEY (OPPORTUNITY_ID) REFERENCES OPPORTUNITIES(ID) ON DELETE CASCADE
);

CREATE INDEX IDX_TRACK_USER ON USER_OPPORTUNITY_TRACKING(USER_ID);
CREATE INDEX IDX_TRACK_STATUS ON USER_OPPORTUNITY_TRACKING(APPLICATION_STATUS);

-- 4. Table: INGESTION_RUNS
-- Tracks provenance, metrics, and error rates of batch opportunity ingestion jobs
CREATE TABLE INGESTION_RUNS (
    ID                  VARCHAR(64)     NOT NULL PRIMARY KEY,
    SOURCE              VARCHAR(64)     NOT NULL,
    RECORDS_PROCESSED   INT             DEFAULT 0,
    RECORDS_INSERTED    INT             DEFAULT 0,
    RECORDS_UPDATED     INT             DEFAULT 0,
    RECORDS_REJECTED    INT             DEFAULT 0,
    STATUS              VARCHAR(32)     DEFAULT 'running', -- 'running', 'completed', 'failed'
    ERROR_SUMMARY       VARCHAR(2048),
    STARTED_AT          TIMESTAMP       DEFAULT CURRENT TIMESTAMP,
    COMPLETED_AT        TIMESTAMP
);

CREATE INDEX IDX_INGEST_STATUS ON INGESTION_RUNS(STATUS);

