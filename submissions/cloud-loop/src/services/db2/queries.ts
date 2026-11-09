/**
 * @file queries.ts
 * @description All IBM Db2 parameterized queries for Cloud Loop.
 * No string-concatenated SQL — all use ? placeholders to prevent injection.
 */

import { executeQuery, type Db2QueryResult } from "./connection";

// ─── Opportunities ───────────────────────────────────────────────────────────

export interface DbOpportunity {
  ID: string;
  TYPE: string;
  TITLE: string;
  COMPANY?: string;
  DESCRIPTION?: string;
  LOCATION?: string;
  LOCATION_TYPE?: string;
  SKILLS?: string;
  SALARY_RANGE?: string;
  DEADLINE?: string;
  APPLY_URL?: string;
  SOURCE?: string;
  EMBEDDING?: string;
  IS_ACTIVE: number;
  CREATED_AT: string;
  UPDATED_AT: string;
}

/**
 * Insert or replace an opportunity in Db2.
 * Uses MERGE for idempotent upsert behaviour.
 */
export async function upsertOpportunity(opp: Omit<DbOpportunity, "CREATED_AT" | "UPDATED_AT">): Promise<Db2QueryResult> {
  const sql = `
    MERGE INTO CLOUDLOOP.OPPORTUNITIES AS tgt
    USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)) AS src
      (ID, TYPE, TITLE, COMPANY, DESCRIPTION, LOCATION, LOCATION_TYPE, SKILLS, SALARY_RANGE, DEADLINE, APPLY_URL, SOURCE, EMBEDDING, IS_ACTIVE)
    ON tgt.ID = src.ID
    WHEN MATCHED THEN
      UPDATE SET TITLE=src.TITLE, COMPANY=src.COMPANY, DESCRIPTION=src.DESCRIPTION,
                 LOCATION=src.LOCATION, LOCATION_TYPE=src.LOCATION_TYPE, SKILLS=src.SKILLS,
                 SALARY_RANGE=src.SALARY_RANGE, DEADLINE=src.DEADLINE, APPLY_URL=src.APPLY_URL,
                 SOURCE=src.SOURCE, EMBEDDING=src.EMBEDDING, IS_ACTIVE=src.IS_ACTIVE,
                 UPDATED_AT=CURRENT_TIMESTAMP
    WHEN NOT MATCHED THEN
      INSERT (ID, TYPE, TITLE, COMPANY, DESCRIPTION, LOCATION, LOCATION_TYPE, SKILLS,
              SALARY_RANGE, DEADLINE, APPLY_URL, SOURCE, EMBEDDING, IS_ACTIVE)
      VALUES (src.ID, src.TYPE, src.TITLE, src.COMPANY, src.DESCRIPTION, src.LOCATION,
              src.LOCATION_TYPE, src.SKILLS, src.SALARY_RANGE, src.DEADLINE, src.APPLY_URL,
              src.SOURCE, src.EMBEDDING, src.IS_ACTIVE)
  `;
  return executeQuery(sql, [
    opp.ID, opp.TYPE, opp.TITLE, opp.COMPANY ?? null, opp.DESCRIPTION ?? null,
    opp.LOCATION ?? null, opp.LOCATION_TYPE ?? null,
    opp.SKILLS ? JSON.stringify(opp.SKILLS) : null,
    opp.SALARY_RANGE ?? null, opp.DEADLINE ?? null,
    opp.APPLY_URL ?? null, opp.SOURCE ?? null,
    opp.EMBEDDING ?? null, opp.IS_ACTIVE,
  ]);
}

/** Fetch active opportunities, optionally filtered by type, with pagination. */
export async function getOpportunities(opts: {
  type?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<Db2QueryResult> {
  const { type, limit = 50, offset = 0 } = opts;
  const sql = type
    ? `SELECT * FROM CLOUDLOOP.OPPORTUNITIES WHERE IS_ACTIVE=1 AND TYPE=? ORDER BY CREATED_AT DESC FETCH FIRST ? ROWS ONLY OFFSET ? ROWS`
    : `SELECT * FROM CLOUDLOOP.OPPORTUNITIES WHERE IS_ACTIVE=1 ORDER BY CREATED_AT DESC FETCH FIRST ? ROWS ONLY OFFSET ? ROWS`;
  return executeQuery(sql, type ? [type, limit, offset] : [limit, offset]);
}

/** Full-text keyword search across title, company, description. */
export async function keywordSearchOpportunities(query: string, limit = 20): Promise<Db2QueryResult> {
  const like = `%${query.toLowerCase()}%`;
  const sql = `
    SELECT * FROM CLOUDLOOP.OPPORTUNITIES
    WHERE IS_ACTIVE=1
      AND (LOWER(TITLE) LIKE ? OR LOWER(COMPANY) LIKE ? OR LOWER(DESCRIPTION) LIKE ? OR LOWER(SKILLS) LIKE ?)
    ORDER BY CREATED_AT DESC
    FETCH FIRST ? ROWS ONLY
  `;
  return executeQuery(sql, [like, like, like, like, limit]);
}

// ─── Search Logging ──────────────────────────────────────────────────────────

/** Log a user search event to Db2. */
export async function logUserSearch(opts: {
  userId?: string;
  query: string;
  resultCount: number;
  sessionId?: string;
}): Promise<Db2QueryResult> {
  return executeQuery(
    `INSERT INTO CLOUDLOOP.USER_SEARCHES (USER_ID, QUERY, RESULT_COUNT, SESSION_ID) VALUES (?, ?, ?, ?)`,
    [opts.userId ?? null, opts.query, opts.resultCount, opts.sessionId ?? null]
  );
}

/** Get the most recent searches for a user (for personalisation). */
export async function getUserRecentSearches(userId: string, limit = 10): Promise<Db2QueryResult> {
  return executeQuery(
    `SELECT QUERY, COUNT(*) AS FREQ FROM CLOUDLOOP.USER_SEARCHES WHERE USER_ID=? GROUP BY QUERY ORDER BY MAX(SEARCHED_AT) DESC FETCH FIRST ? ROWS ONLY`,
    [userId, limit]
  );
}

// ─── Analytics ───────────────────────────────────────────────────────────────

/** Log an analytics event (view, click, search, AI query). */
export async function logAnalyticsEvent(opts: {
  eventType: string;
  metadata?: Record<string, unknown>;
  userId?: string;
  sessionId?: string;
}): Promise<Db2QueryResult> {
  return executeQuery(
    `INSERT INTO CLOUDLOOP.ANALYTICS_EVENTS (EVENT_TYPE, METADATA, USER_ID, SESSION_ID) VALUES (?, ?, ?, ?)`,
    [opts.eventType, opts.metadata ? JSON.stringify(opts.metadata) : null, opts.userId ?? null, opts.sessionId ?? null]
  );
}

/** Get aggregate analytics: top event types count in last N days. */
export async function getAnalyticsSummary(days = 7): Promise<Db2QueryResult> {
  return executeQuery(
    `SELECT EVENT_TYPE, COUNT(*) AS CNT FROM CLOUDLOOP.ANALYTICS_EVENTS WHERE OCCURRED_AT >= CURRENT_TIMESTAMP - ? DAYS GROUP BY EVENT_TYPE ORDER BY CNT DESC`,
    [days]
  );
}

