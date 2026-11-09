-- IBM Db2 schema for Cloud Loop
-- Run via migrations.ts or the IBM Db2 VS Code extension

-- ─────────────────────────────────────────────
-- Opportunities (jobs, internships, events, programs, certifications)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS CLOUDLOOP.OPPORTUNITIES (
  ID             VARCHAR(128)   NOT NULL PRIMARY KEY,
  TYPE           VARCHAR(32)    NOT NULL,         -- 'job' | 'internship' | 'event' | 'program' | 'certification'
  TITLE          VARCHAR(256)   NOT NULL,
  COMPANY        VARCHAR(256),
  DESCRIPTION    CLOB(64K),
  LOCATION       VARCHAR(256),
  LOCATION_TYPE  VARCHAR(32),                      -- 'remote' | 'hybrid' | 'onsite'
  SKILLS         CLOB(16K),                        -- JSON array stored as text
  SALARY_RANGE   VARCHAR(128),
  DEADLINE       VARCHAR(32),
  APPLY_URL      VARCHAR(2048),
  SOURCE         VARCHAR(128),
  EMBEDDING      CLOB(64K),                        -- JSON float array for vector similarity
  IS_ACTIVE      SMALLINT       NOT NULL DEFAULT 1,
  CREATED_AT     TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UPDATED_AT     TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS IDX_OPP_TYPE   ON CLOUDLOOP.OPPORTUNITIES (TYPE);
CREATE INDEX IF NOT EXISTS IDX_OPP_ACTIVE ON CLOUDLOOP.OPPORTUNITIES (IS_ACTIVE);

-- ─────────────────────────────────────────────
-- User search history (for personalisation)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS CLOUDLOOP.USER_SEARCHES (
  ID             BIGINT         NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  USER_ID        VARCHAR(128),
  QUERY          VARCHAR(512)   NOT NULL,
  RESULT_COUNT   INTEGER        DEFAULT 0,
  SESSION_ID     VARCHAR(128),
  SEARCHED_AT    TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS IDX_SRCH_USER ON CLOUDLOOP.USER_SEARCHES (USER_ID);

-- ─────────────────────────────────────────────
-- AI recommendations
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS CLOUDLOOP.AI_RECOMMENDATIONS (
  ID               BIGINT       NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  USER_ID          VARCHAR(128),
  OPPORTUNITY_ID   VARCHAR(128) NOT NULL REFERENCES CLOUDLOOP.OPPORTUNITIES(ID),
  SCORE            DECIMAL(5,4) NOT NULL DEFAULT 0,
  REASON           VARCHAR(512),
  CREATED_AT       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────
-- Analytics events
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS CLOUDLOOP.ANALYTICS_EVENTS (
  ID           BIGINT         NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  EVENT_TYPE   VARCHAR(64)    NOT NULL,   -- 'view' | 'apply_click' | 'search' | 'ai_query'
  METADATA     CLOB(16K),                 -- JSON
  USER_ID      VARCHAR(128),
  SESSION_ID   VARCHAR(128),
  OCCURRED_AT  TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS IDX_EVT_TYPE ON CLOUDLOOP.ANALYTICS_EVENTS (EVENT_TYPE);
CREATE INDEX IF NOT EXISTS IDX_EVT_USER ON CLOUDLOOP.ANALYTICS_EVENTS (USER_ID);

