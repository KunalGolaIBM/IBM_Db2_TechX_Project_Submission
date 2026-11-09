/**
 * IBM Db2 integration (genuine). Uses ibm_db driver.
 * Requires: DB2_HOST, DB2_PORT, DB2_DATABASE, DB2_USERNAME (or DB2_USER), DB2_PASSWORD.
 * Never returns fake successful connection status. Never logs credentials.
 */
import ibmdb from 'ibm_db';

const cfg = () => {
  const user = process.env.DB2_USERNAME || process.env.DB2_USER || '';
  return {
    database: process.env.DB2_DATABASE || '',
    hostname: process.env.DB2_HOST || '',
    port: process.env.DB2_PORT || '50000',
    uid: user,
    pwd: process.env.DB2_PASSWORD || '',
    security: process.env.DB2_SECURITY || '',
  };
};

export function isDb2Configured() {
  const c = cfg();
  return Boolean(c.database && c.hostname && c.uid && c.pwd);
}

export function connStr() {
  const c = cfg();
  const parts = [
    `DATABASE=${c.database}`,
    `HOSTNAME=${c.hostname}`,
    `PORT=${c.port}`,
    'PROTOCOL=TCPIP',
    `UID=${c.uid}`,
    `PWD=${c.pwd}`,
  ];
  if (c.security) parts.push(`SECURITY=${c.security}`);
  return parts.join(';');
}

export async function openDb2() {
  if (!isDb2Configured()) throw new Error('IBM Db2 is not configured. Set DB2_HOST, DB2_PORT, DB2_DATABASE, DB2_USERNAME/DB2_USER, DB2_PASSWORD.');
  return await ibmdb.open(connStr());
}

export async function query(sql, params = []) {
  const conn = await openDb2();
  try {
    const stmt = await conn.prepare(sql);
    try {
      const result = await stmt.execute(params);
      if (Array.isArray(result)) return result;
      if (result && typeof result.fetchAll === 'function') return await result.fetchAll();
      return result;
    } finally {
      await stmt.close().catch(() => {});
    }
  } finally {
    await conn.close().catch(() => {});
  }
}

export async function exec(sql, params = []) {
  const conn = await openDb2();
  try {
    if (!params.length) return await conn.query(sql);
    return await conn.query(sql, params);
  } finally {
    await conn.close().catch(() => {});
  }
}

export async function withTransaction(fn) {
  const conn = await openDb2();
  try {
    await conn.beginTransaction();
    const tx = {
      query: async (sql, params = []) => params.length ? await conn.query(sql, params) : await conn.query(sql),
      exec: async (sql, params = []) => params.length ? await conn.query(sql, params) : await conn.query(sql),
    };
    const out = await fn(tx, conn);
    await conn.commitTransaction();
    return out;
  } catch (e) {
    try { await conn.rollbackTransaction(); } catch {}
    throw e;
  } finally {
    await conn.close().catch(() => {});
  }
}

export async function healthCheck() {
  if (!isDb2Configured()) return { ok: false, configured: false, error: 'IBM Db2 is not configured (missing DB2_* environment variables).' };
  const conn = await openDb2();
  try {
    const rows = await conn.query('SELECT CURRENT SERVER AS SERVER_NAME FROM SYSIBM.SYSDUMMY1');
    const server = Array.isArray(rows) && rows[0] ? (rows[0].SERVER_NAME || rows[0].server_name || rows[0][0] || null) : null;
    return { ok: true, configured: true, database: cfg().database, host: cfg().hostname, port: cfg().port, server, message: 'Connected to IBM Db2.' };
  } finally {
    await conn.close().catch(() => {});
  }
}
