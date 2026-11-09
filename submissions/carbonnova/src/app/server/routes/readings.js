/**
 * CarbonNova — /api/projects/:id/readings, /api/devices, /api/ingest
 * ------------------------------------------------------------------
 * IoT monitoring data access:
 *  - time-range & metric filters, timestamps + units + source labels
 *  - a real ingest endpoint ready for ESP32 / physical sensor nodes
 */
import { Router } from 'express';
import { getDb, saveDb, newId, logActivity } from '../db.js';
import { METRICS } from '../lib/simulator.js';
import { validateIngest } from '../lib/validate.js';

const router = Router();

const RANGE_MS = {
  '24h': 24 * 3600000,
  '7d': 7 * 86400000,
  '30d': 30 * 86400000,
  '90d': 90 * 86400000,
};

/** GET /api/projects/:id/readings?range=24h&limit=500&metric=key */
router.get('/projects/:id/readings', (req, res) => {
  const db = getDb();
  const project = db.projects.find((p) => p.id === req.params.id && p.owner_id === String(req.query.owner || 'user-1'));
  if (!project) return res.status(404).json({ error: 'NOT_FOUND', message: 'Project not found' });

  const range = RANGE_MS[req.query.range] || RANGE_MS['24h'];
  const since = Date.now() - range;
  let readings = db.readings.filter(
    (r) => r.project_id === project.id && new Date(r.recorded_at).getTime() >= since
  );
  const limit = Math.min(Number(req.query.limit) || 1000, 5000);
  readings = readings.slice(-limit);

  const metric = req.query.metric && METRICS.some((m) => m.key === req.query.metric) ? req.query.metric : null;

  res.json({
    project_id: project.id,
    range: req.query.range || '24h',
    metric,
    metrics_available: METRICS,
    count: readings.length,
    data_sources: [...new Set(readings.map((r) => r.data_source))],
    all_simulated: readings.length > 0 && readings.every((r) => r.is_simulated),
    readings,
  });
});

/** GET /api/projects/:id/devices */
router.get('/projects/:id/devices', (req, res) => {
  const db = getDb();
  const devices = db.devices.filter((d) => d.project_id === req.params.id);
  const enriched = devices.map((d) => {
    const readings = db.readings.filter((r) => r.device_id === d.id);
    const last = readings[readings.length - 1];
    return { ...d, reading_count: readings.length, last_reading_at: last?.recorded_at ?? null };
  });
  res.json({ devices: enriched });
});

/** GET /api/devices — all devices (dashboard view). */
router.get('/devices', (req, res) => {
  const db = getDb();
  const devices = db.devices.map((d) => {
    const readings = db.readings.filter((r) => r.device_id === d.id);
    const last = readings[readings.length - 1];
    const project = db.projects.find((p) => p.id === d.project_id);
    return {
      ...d,
      project_name: project?.name ?? null,
      reading_count: readings.length,
      last_reading_at: last?.recorded_at ?? null,
      latest_values: last?.values ?? null,
    };
  });
  res.json({ devices });
});

/**
 * POST /api/ingest — physical sensor (ESP32) ingest endpoint.
 * Body: { device_token, readings: { soil_moisture_pct, soil_temp_c, … } }
 * Stores a real (non-simulated) timestamped record labelled data_source:'device'.
 * This is the production entry point for field hardware.
 */
router.post('/ingest', (req, res) => {
  const errors = validateIngest(req.body);
  if (errors.length) return res.status(400).json({ error: 'VALIDATION_ERROR', details: errors });

  const db = getDb();
  const device = db.devices.find((d) => d.device_token === req.body.device_token);
  if (!device) return res.status(401).json({ error: 'INVALID_DEVICE_TOKEN', message: 'Unknown device_token. Pair the device first.' });

  const values = {};
  for (const [k, v] of Object.entries(req.body.readings)) {
    if (v !== undefined && v !== null && Number.isFinite(Number(v))) values[k] = Number(v);
  }
  const reading = {
    id: newId('rdg'),
    device_id: device.id,
    project_id: device.project_id,
    recorded_at: req.body.recorded_at && !Number.isNaN(Date.parse(req.body.recorded_at))
      ? new Date(req.body.recorded_at).toISOString()
      : new Date().toISOString(),
    data_source: 'device',
    is_simulated: false,
    values,
  };
  db.readings.push(reading);
  device.is_active = true;
  device.last_ping = reading.recorded_at;
  if (reading.recorded_at > (device.last_reading_at || '')) device.last_reading_at = reading.recorded_at;

  // Keep the store bounded (~5k most recent readings)
  if (db.readings.length > 20000) db.readings.splice(0, db.readings.length - 20000);

  logActivity({
    project_id: device.project_id, type: 'reading_ingested', source: 'device',
    message: `Real sensor reading received from device ${device.id} (${device.name}) at ${reading.recorded_at}.`,
  });
  saveDb();
  res.status(201).json({ stored: true, reading });
});

export default router;
