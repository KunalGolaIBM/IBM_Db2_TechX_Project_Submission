/**
 * CarbonNova — /api/projects routes
 * Land & project management with validation and an activity/audit trail.
 */
import { Router } from 'express';
import { getDb, saveDb, newId, logActivity, ACRES_TO_HA } from '../db.js';
import { validateProjectInput } from '../lib/validate.js';

const router = Router();

const round = (v, dp = 2) => Number(v.toFixed(dp));

/** Attach live summary stats to a project (readings count, latest values, sensors). */
function withSummary(project) {
  const db = getDb();
  const readings = db.readings.filter((r) => r.project_id === project.id);
  const devices = db.devices.filter((d) => d.project_id === project.id);
  const latest = readings.length ? readings[readings.length - 1] : null;
  const last24h = readings.filter((r) => Date.now() - new Date(r.recorded_at).getTime() < 86400000);
  return {
    ...project,
    area_hectares: round((project.area_acres || 0) * ACRES_TO_HA, 2),
    device_count: devices.length,
    devices_online: devices.filter((d) => d.is_active !== false).length,
    reading_count: readings.length,
    readings_last_24h: last24h.length,
    latest_reading: latest
      ? { recorded_at: latest.recorded_at, values: latest.values, data_source: latest.data_source, is_simulated: latest.is_simulated }
      : null,
    last_reading_at: latest?.recorded_at ?? null,
  };
}

// List projects for the current demo owner. Real deployments must replace this identity with authenticated claims.
router.get('/projects', (req, res) => {
  const db = getDb();
  const ownerId = String(req.query.owner || 'user-1');
  const projects = db.projects.filter((project) => project.owner_id === ownerId);
  res.json({ projects: projects.map(withSummary) });
});

// Read one project
router.get('/projects/:id', (req, res) => {
  const db = getDb();
  const project = db.projects.find((p) => p.id === req.params.id && p.owner_id === String(req.query.owner || 'user-1'));
  if (!project) return res.status(404).json({ error: 'NOT_FOUND', message: `Project ${req.params.id} not found` });
  const activity = db.activity.filter((a) => a.project_id === project.id);
  res.json({ project: withSummary(project), activity });
});

// Create a project
router.post('/projects', (req, res) => {
  const errors = validateProjectInput(req.body);
  if (errors.length) return res.status(400).json({ error: 'VALIDATION_ERROR', details: errors });

  const db = getDb();
  const now = new Date().toISOString();
  const ownerId = String(req.body.owner_id || 'user-1');
  const project = {
    id: newId('proj'),
    owner_id: ownerId,
    name: req.body.name.trim(),
    land_type: req.body.land_type,
    area_acres: Number(req.body.area_acres),
    location: req.body.location?.trim() || null,
    latitude: req.body.latitude !== undefined && req.body.latitude !== '' ? Number(req.body.latitude) : null,
    longitude: req.body.longitude !== undefined && req.body.longitude !== '' ? Number(req.body.longitude) : null,
    status: req.body.status || 'active',
    description: req.body.description?.trim() || null,
    created_at: now,
    updated_at: now,
  };
  db.projects.push(project);
  logActivity({ project_id: project.id, type: 'project_created', source: 'user', message: `Monitoring project "${project.name}" created (${project.area_acres} acres, ${project.land_type}).` });
  saveDb();
  res.status(201).json({ project: withSummary(project) });
});

// Update a project
router.patch('/projects/:id', (req, res) => {
  const db = getDb();
  const project = db.projects.find((p) => p.id === req.params.id && p.owner_id === String(req.body?.owner_id || req.query.owner || 'user-1'));
  if (!project) return res.status(404).json({ error: 'NOT_FOUND', message: `Project ${req.params.id} not found` });

  const errors = validateProjectInput(req.body, { partial: true });
  if (errors.length) return res.status(400).json({ error: 'VALIDATION_ERROR', details: errors });

  const fields = ['name', 'land_type', 'location', 'status', 'description'];
  for (const f of fields) if (req.body[f] !== undefined) project[f] = typeof req.body[f] === 'string' ? req.body[f].trim() : req.body[f];
  if (req.body.area_acres !== undefined) project.area_acres = Number(req.body.area_acres);
  if (req.body.soc_pct !== undefined) project.soc_pct = Number(req.body.soc_pct);
  if (req.body.bulk_density !== undefined) project.bulk_density = Number(req.body.bulk_density);
  if (req.body.latitude !== undefined) project.latitude = req.body.latitude === '' || req.body.latitude === null ? null : Number(req.body.latitude);
  if (req.body.longitude !== undefined) project.longitude = req.body.longitude === '' || req.body.longitude === null ? null : Number(req.body.longitude);
  project.updated_at = new Date().toISOString();

  logActivity({ project_id: project.id, type: 'project_updated', source: 'user', message: `Project details updated (${Object.keys(req.body).join(', ')}).` });
  saveDb();
  res.json({ project: withSummary(project) });
});

// Delete a project (keeps orphaned readings out of the store)
router.delete('/projects/:id', (req, res) => {
  const db = getDb();
  const idx = db.projects.findIndex((p) => p.id === req.params.id && p.owner_id === String(req.query.owner || 'user-1'));
  if (idx === -1) return res.status(404).json({ error: 'NOT_FOUND', message: `Project ${req.params.id} not found` });
  const [project] = db.projects.splice(idx, 1);
  db.devices = db.devices.filter((d) => d.project_id !== project.id);
  const removedReadings = db.readings.length;
  db.readings = db.readings.filter((r) => r.project_id !== project.id);
  db.parcels = db.parcels.filter((parcel) => parcel.project_id !== project.id);
  db.assessments = db.assessments.filter((assessment) => assessment.project_id !== project.id);
  logActivity({ project_id: null, type: 'project_deleted', source: 'user', message: `Project "${project.name}" deleted; ${removedReadings - db.readings.length} readings removed from active store.` });
  saveDb();
  res.json({ deleted: true, id: project.id, readings_removed: removedReadings - db.readings.length });
});

export default router;
