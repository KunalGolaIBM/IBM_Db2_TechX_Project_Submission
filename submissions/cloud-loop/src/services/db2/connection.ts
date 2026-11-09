/**
 * @file connection.ts
 * @description IBM Db2 connection layer.
 * Gracefully degrades if ibm_db is not installed or credentials are absent.
 */

import { db2Config } from "@/config/env";

export interface Db2QueryResult {
  rows: Record<string, unknown>[];
  rowCount: number;
}

/** Build a Db2 DSN connection string */
function buildDsn(): string {
  if (db2Config.sslDsn) return db2Config.sslDsn;
  return (
    `DATABASE=${db2Config.database};` +
    `HOSTNAME=${db2Config.hostname};` +
    `PORT=${db2Config.port};` +
    `PROTOCOL=TCPIP;` +
    `UID=${db2Config.uid};` +
    `PWD=${db2Config.pwd};` +
    (db2Config.ssl ? "Security=SSL;" : "")
  );
}

interface IbmDbDriver {
  open: (dsn: string, cb: (err: Error | null, conn: any) => void) => void;
  openSync: (dsn: string) => any;
  [key: string]: unknown;
}

let ibmDb: IbmDbDriver | null = null;

/**
 * Lazily load ibm_db — it's an optional native addon.
 * Returns null and logs a warning when not available.
 */
async function loadIbmDb(): Promise<IbmDbDriver | null> {
  if (ibmDb) return ibmDb;
  try {
    const pkg = "ibm_db";
    ibmDb = (await Function("p", "return import(p)")(pkg)) as IbmDbDriver;
    return ibmDb;
  } catch {
    console.warn(
      "[Db2] ibm_db is not installed. Run: npm install ibm_db --legacy-peer-deps\n" +
      "[Db2] Db2 features will be disabled until the driver is available."
    );
    return null;
  }
}

/**
 * Execute a parameterized SQL query against IBM Db2.
 * Returns an empty result set when Db2 is not configured/available.
 *
 * @param sql - Parameterized SQL string with ? placeholders
 * @param params - Positional parameter values
 */
export async function executeQuery(
  sql: string,
  params: unknown[] = []
): Promise<Db2QueryResult> {
  if (!db2Config.isConfigured) {
    console.warn("[Db2] Credentials not configured — skipping query.");
    return { rows: [], rowCount: 0 };
  }

  const driver = await loadIbmDb();
  if (!driver) return { rows: [], rowCount: 0 };

  return new Promise((resolve) => {
    driver.open(buildDsn(), (err: Error | null, conn: { query: (s: string, p: unknown[], cb: (qErr: Error | null, d: unknown) => void) => void; close: (cb: () => void) => void }) => {
      if (err || !conn) {
        console.error("[Db2] Connection error:", err?.message);
        resolve({ rows: [], rowCount: 0 });
        return;
      }

      conn.query(sql, params, (queryErr: Error | null, data: unknown) => {
        conn.close(() => { });
        if (queryErr) {
          console.error("[Db2] Query error:", queryErr.message, "\nSQL:", sql);
          resolve({ rows: [], rowCount: 0 });
          return;
        }
        const rows = Array.isArray(data) ? (data as Record<string, unknown>[]) : [];
        resolve({ rows, rowCount: rows.length });
      });
    });
  });
}

/**
 * Test the Db2 connection.
 * @returns true if the connection is successful
 */
export async function testConnection(): Promise<boolean> {
  try {
    const result = await executeQuery("SELECT 1 FROM SYSIBM.SYSDUMMY1");
    return result.rowCount > 0;
  } catch {
    return false;
  }
}

