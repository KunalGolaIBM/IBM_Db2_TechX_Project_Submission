/** Integration tests — CarbonNova API (in-memory DB, no Nebius key). Run: npm test */
import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';

// Environment MUST be set before importing the server modules.
process.env.CARBONNOVA_MEM = '1';
process.env.CARBONNOVA_NO_SEED = '1';
process.env.NODE_ENV = 'test';
process.env.CARBONNOVA_DATA_DIR = '';

const { createApp } = await import('../index.js');
const { resetDb, getDb } = await import('../db.js');
const { seedDemoData } = await import('../seed.js');

let server;
let base;

before(async () => {
  delete process.env.NEBIUS_API_KEY; // AI must be in "not configured" state
  resetDb();
  seedDemoData(true);
  const app = createApp();
  server = app.listen(0);
  await once(server, 'listening');
  base = `http://127.0.0.1:${server.address().port}`;
});

after(() => server.close());

const get = (p) => fetch(base + p);
const post = (p, body) => fetch(base + p, {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body ?? {}),
});
const patch = (p, body) => fetch(base + p, {
  method: 'PATCH', headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body ?? {}),
});
const del = (p) => fetch(base + p, { method: 'DELETE' });

describe('health & status', () => {
  test('GET /api/health returns ok + stats + AI flag', async () => {
    const res = await get('/api/health');
    assert.equal(res.status, 200);
    const j = await res.json();
    assert.equal(j.ok, true);
    assert.equal(j.stats.projects, 3);
    assert.ok(j.stats.readings > 0);
    assert.equal(j.ai.configured, false);
    assert.match(j.ai.model, /nemotron/i);
  });

  test('GET /api/ai/status never exposes a key', async () => {
    const res = await get('/api/ai/status');
    const j = await res.json();
    assert.equal(res.status, 200);
    assert.equal(j.configured, false);
    assert.ok(j.base_url.includes('tokenfactory.nebius.com'));
    const raw = JSON.stringify(j);
    assert.ok(!/api.?key/i.test(raw.replace(/base_url/g, '')) || !raw.includes('sk-'));
  });

  test('GET /api/activity returns timestamped audit events', async () => {
    const j = await (await get('/api/activity')).json();
    assert.ok(j.activity.length > 0);
    assert.ok(j.activity.every((a) => a.at && a.type && a.message));
  });
});

describe('projects CRUD + validation', () => {
  let createdId;

  test('rejects invalid project with 400 + details', async () => {
    const res = await post('/api/projects', { name: 'x', land_type: 'wetland', area_acres: -5 });
    assert.equal(res.status, 400);
    const j = await res.json();
    assert.equal(j.error, 'VALIDATION_ERROR');
    assert.ok(j.details.some((d) => d.includes('land_type')));
    assert.ok(j.details.some((d) => d.includes('area_acres')));
  });

  test('creates, reads, updates and deletes a project', async () => {
    const res = await post('/api/projects', {
      name: 'Konkan Coastal Cropland', land_type: 'cropland', area_acres: 55,
      location: 'Ratnagiri, Maharashtra', description: 'Test project flow',
    });
    assert.equal(res.status, 201);
    const { project } = await res.json();
    createdId = project.id;
    assert.equal(project.area_acres, 55);
    assert.ok(project.area_hectares > 0);
    assert.equal(project.reading_count, 0);
    assert.equal(project.latest_reading, null);

    const read = await get(`/api/projects/${createdId}`);
    assert.equal(read.status, 200);
    const detail = await read.json();
    assert.equal(detail.project.name, 'Konkan Coastal Cropland');
    assert.ok(detail.activity.some((a) => a.type === 'project_created'), 'creation must be audited');

    const upd = await patch(`/api/projects/${createdId}`, { area_acres: 60, status: 'paused' });
    assert.equal(upd.status, 200);
    assert.equal((await upd.json()).project.area_acres, 60);

    const rm = await del(`/api/projects/${createdId}`);
    assert.equal(rm.status, 200);
    assert.equal((await get(`/api/projects/${createdId}`)).status, 404);
  });

  test('listing supports owner filter and returns live summaries', async () => {
    const j = await (await get('/api/projects?owner=user-1')).json();
    assert.equal(j.projects.length, 3);
    const p = j.projects.find((x) => x.id === 'proj-sahyadri');
    assert.ok(p.latest_reading, 'seeded project must have a latest reading');
    assert.equal(p.latest_reading.is_simulated, true, 'simulated label must propagate');
    assert.equal(p.device_count, 1);
  });

  test('unknown project → structured 404', async () => {
    const res = await get('/api/projects/proj_nope');
    assert.equal(res.status, 404);
    assert.equal((await res.json()).error, 'NOT_FOUND');
  });
});

describe('sensor readings (IoT monitoring)', () => {
  test('range filter + metric availability + simulated labeling', async () => {
    const res = await get('/api/projects/proj-sahyadri/readings?range=24h');
    assert.equal(res.status, 200);
    const j = await res.json();
    assert.ok(j.count > 0);
    assert.equal(j.all_simulated, true);
    assert.ok(j.metrics_available.some((m) => m.key === 'soil_co2_respiration'));
    assert.ok(j.readings.every((r) => r.recorded_at && r.data_source === 'simulated'));
    // all timestamps within 24h
    const newest = new Date(j.readings[j.readings.length - 1].recorded_at).getTime();
    assert.ok(Date.now() - newest < 26 * 3600000);
  });

  test('longer range returns more readings than 24h', async () => {
    const day = (await (await get('/api/projects/proj-sahyadri/readings?range=24h')).json()).count;
    const month = (await (await get('/api/projects/proj-sahyadri/readings?range=30d')).json()).count;
    assert.ok(month > day, `expected 30d (${month}) > 24h (${day})`);
  });

  test('devices endpoint exposes status + last ping', async () => {
    const j = await (await get('/api/devices')).json();
    assert.equal(j.devices.length, 3);
    assert.ok(j.devices.every((d) => d.project_name && d.last_reading_at));
  });
});

describe('ESP32 ingest endpoint (physical sensors)', () => {
  test('rejects bad token with 401', async () => {
    const res = await post('/api/ingest', { device_token: 'tok-invalid-xxx', readings: { soil_moisture_pct: 40 } });
    assert.equal(res.status, 401);
    assert.equal((await res.json()).error, 'INVALID_DEVICE_TOKEN');
  });

  test('rejects invalid payloads with 400', async () => {
    assert.equal((await post('/api/ingest', { device_token: 'tok-sahyadri-demo-001' })).status, 400);
    const res = await post('/api/ingest', { device_token: 'tok-sahyadri-demo-001', readings: { soil_ph: 14.5 } });
    assert.equal(res.status, 400);
    const j = await res.json();
    assert.ok(j.details.some((d) => d.includes('soil_ph')));
  });

  test('stores real device data labelled data_source=device, is_simulated=false', async () => {
    const before = (await (await get('/api/projects/proj-sahyadri/readings?range=24h')).json()).count;
    const res = await post('/api/ingest', {
      device_token: 'tok-sahyadri-demo-001',
      readings: { soil_moisture_pct: 41.2, soil_temp_c: 24.8, soil_co2_respiration: 310, soil_ph: 6.6, ec_ds_m: 0.85 },
    });
    assert.equal(res.status, 201);
    const { reading } = await res.json();
    assert.equal(reading.data_source, 'device');
    assert.equal(reading.is_simulated, false);
    assert.ok(reading.recorded_at);

    const after = await (await get('/api/projects/proj-sahyadri/readings?range=24h')).json();
    assert.ok(after.count > before);
    assert.ok(after.readings.some((r) => r.data_source === 'device'), 'device reading must appear in series');
    assert.ok(after.all_simulated === false, 'series must no longer be flagged all-simulated');

    const acts = await (await get('/api/activity?limit=20')).json();
    assert.ok(acts.activity.some((a) => a.source === 'device' && a.type === 'reading_ingested'));
  });
});

describe('saved parcel mapping and assessment ledger', () => {
  test('creates, measures, lists, updates and deletes parcel records', async () => {
    const coordinates = [[18.5, 73.8], [18.5, 73.81], [18.51, 73.81], [18.51, 73.8]];
    const res = await post('/api/parcels', { name: 'Test farm parcel', coordinates, owner_id: 'user-1' });
    assert.equal(res.status, 201);
    const { parcel, project } = await res.json();
    assert.ok(parcel.area_m2 > 0 && parcel.area_hectares > 0 && parcel.area_acres > 0);
    assert.equal(parcel.project_id, project.id);
    assert.equal(project.status, 'data_collection');
    assert.equal((await get('/api/parcels?owner_id=user-1')).status, 200);
    assert.equal((await get('/api/projects?owner=user-1')).status, 200);

    const updated = await fetch(`${base}/api/parcels/${parcel.id}`, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ name: 'Renamed parcel' }) });
    assert.equal((await updated.json()).parcel.name, 'Renamed parcel');
    const removed = await fetch(`${base}/api/parcels/${parcel.id}?owner_id=user-1`, { method: 'DELETE' });
    assert.equal(removed.status, 200);
    assert.equal((await fetch(`${base}/api/parcels/${parcel.id}?owner_id=somebody-else`)).status, 404);
  });

  test('rejects malformed polygon geometry without persisting it', async () => {
    const res = await post('/api/parcels', { name: 'Bad boundary', coordinates: [[0, 0], [0, 1], [1, 0], [1, 1]] });
    assert.equal(res.status, 400);
    assert.equal((await res.json()).error, 'INVALID_GEOMETRY');
  });

  test('creates reproducible ledger revisions with linked inputs and pending review', async () => {
    const first = await post('/api/projects/proj-sahyadri/assessments', {});
    assert.equal(first.status, 201);
    const a = (await first.json()).assessment;
    assert.equal(a.human_review_status, 'pending');
    assert.ok(a.input_observation_ids.length > 0);
    assert.equal(a.estimate.assessment_classification.includes('not verified'), true);
    const second = (await post('/api/projects/proj-sahyadri/assessments', {})).json();
    const b = (await second).assessment;
    assert.equal(b.revision, a.revision + 1);
    assert.equal(b.previous_assessment_id, a.id);
    const listed = await (await get('/api/projects/proj-sahyadri/assessments')).json();
    assert.equal(listed.assessments.length, 2);
  });
});

describe('carbon estimation endpoint (science layer)', () => {
  test('returns explainable estimate with formulas/assumptions/disclaimer', async () => {
    const res = await get('/api/projects/proj-sahyadri/carbon?range=30d');
    assert.equal(res.status, 200);
    const j = await res.json();
    assert.ok(j.estimate.metrics.soc_stock_total_tC > 0);
    assert.ok(j.estimate.metrics.net_sequestration_uncertainty.pct > 0);
    assert.ok(j.estimate.formulas.length >= 4);
    assert.ok(j.estimate.assumptions.length >= 4);
    assert.match(j.estimate.disclaimer, /NOT A VERIFIED CARBON CREDIT/i);
    assert.equal(j.methodology.engine_version, '1.0.0');
    assert.ok(j.period.readings_used > 0);
  });

  test('separation: carbon endpoint never invokes AI (no model fields in response)', async () => {
    const j = await (await get('/api/projects/proj-sahyadri/carbon')).json();
    const raw = JSON.stringify(j);
    assert.ok(!raw.includes('answer'), 'carbon response must not contain AI answer');
    assert.ok(!raw.includes('choices'), 'carbon response must not contain LLM payload');
  });
});

describe('AI assistant failure handling (no key, no fabrication)', () => {
  test('ask returns 503 AI_NOT_CONFIGURED with actionable message, no fake answer', async () => {
    const res = await post('/api/projects/proj-sahyadri/ai/ask', { question: 'Summarize soil moisture trends' });
    assert.equal(res.status, 503);
    const j = await res.json();
    assert.equal(j.error, 'AI_NOT_CONFIGURED');
    assert.equal(j.retryable, true);
    assert.match(j.message, /NEBIUS_API_KEY/);
    assert.equal(j.answer, undefined, 'MUST NOT fabricate an AI answer');
  });

  test('preset route validates the preset name', async () => {
    const res = await post('/api/projects/proj-sahyadri/ai/preset', { preset: 'hallucinate' });
    assert.equal(res.status, 400);
    assert.equal((await res.json()).error, 'VALIDATION_ERROR');
  });

  test('question validation: too short → 400', async () => {
    const res = await post('/api/projects/proj-sahyadri/ai/ask', { question: 'a' });
    assert.equal(res.status, 400);
  });

  test('failed AI attempt is recorded in the audit trail', async () => {
    await post('/api/projects/proj-sahyadri/ai/ask', { question: 'Any unusual readings?' });
    const acts = await (await get('/api/activity?limit=50')).json();
    assert.ok(acts.activity.some((a) => a.type === 'ai_error'));
  });
});

describe('MRV reports', () => {
  test('CSV readings export contains source labels + disclaimer', async () => {
    const res = await post('/api/projects/proj-sahyadri/reports/csv', { kind: 'readings' });
    assert.equal(res.status, 200);
    assert.match(res.headers.get('content-type'), /text\/csv/);
    assert.ok(res.headers.get('content-disposition').includes('attachment'));
    const csv = await res.text();
    assert.match(csv, /recorded_at,device_id,data_source,is_simulated/);
    assert.match(csv, /simulated/);
    assert.match(csv, /disclaimer/i);
  });

  test('CSV carbon-estimate export includes formulas', async () => {
    const csv = await (await post('/api/projects/proj-sahyadri/reports/csv', { kind: 'carbon' })).text();
    assert.match(csv, /formula,soc_stock/);
    assert.match(csv, /assumption/);
    assert.match(csv, /limitation/);
  });

  test('PDF report is a real PDF (%PDF) and audited', async () => {
    const res = await post('/api/projects/proj-sahyadri/reports/pdf', {});
    assert.equal(res.status, 200);
    assert.match(res.headers.get('content-type'), /application\/pdf/);
    assert.ok(res.headers.get('x-report-id'));
    const buf = Buffer.from(await res.arrayBuffer());
    assert.ok(buf.length > 1000, `PDF too small: ${buf.length}`);
    assert.equal(buf.subarray(0, 5).toString('latin1'), '%PDF-');

    const reports = await (await get('/api/projects/proj-sahyadri/reports')).json();
    assert.ok(reports.reports.some((r) => r.type === 'pdf' && r.readings_count > 0));
  });

  test('PDF with AI summary requested but AI unconfigured → still succeeds, error flagged in header (no fabrication)', async () => {
    const res = await post('/api/projects/proj-sahyadri/reports/pdf', { include_ai_summary: true });
    assert.equal(res.status, 200);
    assert.ok(res.headers.get('x-ai-summary-error'), 'must expose why AI summary is missing');
    const buf = Buffer.from(await res.arrayBuffer());
    assert.equal(buf.subarray(0, 5).toString('latin1'), '%PDF-');
    const reports = await (await get('/api/projects/proj-sahyadri/reports')).json();
    assert.ok(!reports.reports[0].includes_ai_content, 'report must not claim AI content when absent');
  });
});

describe('robustness', () => {
  test('invalid JSON body → 400 INVALID_JSON', async () => {
    const res = await fetch(base + '/api/projects', {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: '{bad json',
    });
    assert.equal(res.status, 400);
    assert.equal((await res.json()).error, 'INVALID_JSON');
  });

  test('unknown API route → structured 404', async () => {
    const res = await get('/api/nope');
    assert.equal(res.status, 404);
    assert.equal((await res.json()).error, 'NOT_FOUND');
  });

  test('oversized body → 413', async () => {
    const res = await post('/api/projects', { name: 'x'.repeat(300 * 1024) });
    assert.equal(res.status, 413);
    assert.equal((await res.json()).error, 'PAYLOAD_TOO_LARGE');
  });
});
