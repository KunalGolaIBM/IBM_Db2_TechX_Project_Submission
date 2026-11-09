/**
 * CarbonNova — Data layer
 * -----------------------
 * Lightweight JSON-file persistence (no native deps, works everywhere).
 * Every record is timestamped and labelled with its data source so the
 * platform keeps an audit-friendly trail from raw readings to indicators
 * to reports (data-integrity requirement #9).
 *
 * Set CARBONNOVA_MEM=1 to run fully in-memory (used by the test suite).
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = process.env.CARBONNOVA_DATA_DIR || path.join(__dirname, 'data');
const DATA_FILE = process.env.CARBONNOVA_MEM ? null : path.join(DATA_DIR, 'db.json');

export const ACRES_TO_HA = 0.0404686;

const EMPTY_DB = {
  meta: { created_at: new Date().toISOString(), schema_version: 2 },
  users: [],
  profiles: [],
  projects: [],
  parcels: [],
  assessments: [],
  devices: [],
  readings: [],
  activity: [],
  reports: [],
  // CarbonNova marketplace / governance (demo)
  land_registrations: [],
  carbon_projects: [],      // submitted/verified project workflow records
  credit_listings: [],
  credit_balances: [],
  credit_transactions: [],
  project_documents: [],
  verification_records: [],
  admin_actions: [],
  audit_logs: [],
};

let db = null;
const listeners = new Set();

function load() {
  if (process.env.CARBONNOVA_MEM || !fs.existsSync(DATA_FILE)) {
    return structuredClone(EMPTY_DB);
  }
  try {
    const raw = fs.readFileSync(DATA_FILE, 'utf8');
    const parsed = JSON.parse(raw);
    return {
      ...structuredClone(EMPTY_DB),
      ...parsed,
      parcels: parsed.parcels || [],
      assessments: parsed.assessments || [],
      profiles: parsed.profiles || [],
      land_registrations: parsed.land_registrations || [],
      carbon_projects: parsed.carbon_projects || [],
      credit_listings: parsed.credit_listings || [],
      credit_balances: parsed.credit_balances || [],
      credit_transactions: parsed.credit_transactions || [],
      project_documents: parsed.project_documents || [],
      verification_records: parsed.verification_records || [],
      admin_actions: parsed.admin_actions || [],
      audit_logs: parsed.audit_logs || [],
    };
  } catch (err) {
    console.error('[db] Failed to parse db.json, starting fresh:', err.message);
    return structuredClone(EMPTY_DB);
  }
}

let saveTimer = null;
function persist() {
  if (!DATA_FILE) return;
  // Debounced write to avoid hammering the disk during bulk seeding
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try {
      fs.mkdirSync(DATA_DIR, { recursive: true });
      const tmp = DATA_FILE + '.tmp';
      fs.writeFileSync(tmp, JSON.stringify(db, null, 1));
      fs.renameSync(tmp, DATA_FILE);
    } catch (err) {
      console.error('[db] Failed to persist:', err.message);
    }
  }, 50);
}

export function getDb() {
  if (!db) db = load();
  return db;
}

export function saveDb() {
  getDb();
  persist();
  listeners.forEach((fn) => {
    try { fn(db); } catch { /* listener errors must not break writes */ }
  });
}

export function onChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** Reset the database (test helper). */
export function resetDb(seedFn) {
  db = structuredClone(EMPTY_DB);
  if (seedFn) seedFn(db);
  saveDb();
  return db;
}

export const newId = (prefix) =>
  `${prefix}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;

/** Append a timestamped, source-labelled activity/audit event. */
export function logActivity({ project_id = null, type, message, source = 'system', severity = 'info' }) {
  const d = getDb();
  const entry = {
    id: newId('act'),
    project_id,
    type,
    message,
    source,
    severity,
    at: new Date().toISOString(),
  };
  d.activity.unshift(entry);
  if (d.activity.length > 2000) d.activity.length = 2000;
  return entry;
}

/** Append an auditable platform action (admin/governance/transactions). */
export function logAudit({ actor_id = null, actor_role = null, action, entity_type, entity_id = null, before = null, after = null, reason = null, source = 'system' }) {
  const d = getDb();
  const entry = {
    id: newId('audit'),
    actor_id,
    actor_role,
    action,
    entity_type,
    entity_id,
    before,
    after,
    reason,
    source,
    at: new Date().toISOString(),
  };
  d.audit_logs.unshift(entry);
  if (d.audit_logs.length > 5000) d.audit_logs.length = 5000;
  return entry;
}
