import { Router } from 'express';
import { getDb, saveDb, newId, logActivity } from '../db.js';
import { measureParcel } from '../lib/geometry.js';

const router = Router();
const ownerMatches = (parcel, ownerId) => parcel.owner_id === ownerId;

router.get('/parcels', (req, res) => {
  const ownerId = String(req.query.owner_id || 'user-1');
  const parcels = getDb().parcels.filter((parcel) => ownerMatches(parcel, ownerId));
  res.json({ parcels });
});

router.post('/parcels', (req, res) => {
  const name = typeof req.body?.name === 'string' ? req.body.name.trim() : '';
  if (name.length < 2 || name.length > 120) {
    return res.status(400).json({ error: 'VALIDATION_ERROR', details: ['name must be between 2 and 120 characters'] });
  }
  let geometry;
  try {
    geometry = measureParcel(req.body?.coordinates);
  } catch (error) {
    return res.status(400).json({ error: 'INVALID_GEOMETRY', message: error.message });
  }
  const ownerId = String(req.body?.owner_id || 'user-1').slice(0, 100);
  const now = new Date().toISOString();
  const landType = ['agroforestry', 'forestry', 'cropland', 'pasture', 'mangrove', 'solar', 'biogas'].includes(req.body.land_type) ? req.body.land_type : 'cropland';
  const location = typeof req.body.location === 'string' ? req.body.location.trim().slice(0, 200) : null;
  const db = getDb();
  const project = {
    id: newId('proj'), owner_id: ownerId, name, land_type: landType,
    area_acres: geometry.area_acres, location, latitude: geometry.coordinates[0][0], longitude: geometry.coordinates[0][1],
    status: 'data_collection', description: 'Created from a user-drawn parcel boundary. Boundary is not a cadastral survey; collect field evidence before carbon-credit project claims.',
    created_at: now, updated_at: now,
  };
  const parcel = {
    id: newId('parcel'), owner_id: ownerId, project_id: project.id, name, location,
    land_type: landType, ...geometry,
    mapping_source: 'user-drawn map boundary', mapping_date: now,
    area_method: 'Spherical geodesic polygon area (WGS84-style mean Earth radius); not a cadastral survey.',
    created_at: now, updated_at: now, revision: 1,
  };
  db.projects.push(project);
  db.parcels.push(parcel);
  logActivity({ project_id: project.id, type: 'parcel_created', source: 'user', message: `Parcel boundary "${name}" saved (${parcel.area_hectares} ha); user-mapped, not legally verified.` });
  saveDb();
  return res.status(201).json({ parcel, project });
});

router.patch('/parcels/:id', (req, res) => {
  const db = getDb();
  const ownerId = String(req.body?.owner_id || req.query.owner_id || 'user-1');
  const parcel = db.parcels.find((item) => item.id === req.params.id && ownerMatches(item, ownerId));
  if (!parcel) return res.status(404).json({ error: 'NOT_FOUND', message: 'Parcel not found.' });
  if (req.body?.name !== undefined) {
    if (typeof req.body.name !== 'string' || req.body.name.trim().length < 2 || req.body.name.trim().length > 120) {
      return res.status(400).json({ error: 'VALIDATION_ERROR', details: ['name must be between 2 and 120 characters'] });
    }
    parcel.name = req.body.name.trim();
  }
  if (req.body?.coordinates !== undefined) {
    let geometry;
    try { geometry = measureParcel(req.body.coordinates); }
    catch (error) { return res.status(400).json({ error: 'INVALID_GEOMETRY', message: error.message }); }
    Object.assign(parcel, geometry);
  }
  parcel.revision += 1;
  parcel.updated_at = new Date().toISOString();
  logActivity({ type: 'parcel_updated', source: 'user', message: `Parcel boundary "${parcel.name}" updated to revision ${parcel.revision}.` });
  saveDb();
  return res.json({ parcel });
});

router.delete('/parcels/:id', (req, res) => {
  const db = getDb();
  const ownerId = String(req.query.owner_id || 'user-1');
  const index = db.parcels.findIndex((item) => item.id === req.params.id && ownerMatches(item, ownerId));
  if (index < 0) return res.status(404).json({ error: 'NOT_FOUND', message: 'Parcel not found.' });
  const [parcel] = db.parcels.splice(index, 1);
  logActivity({ type: 'parcel_deleted', source: 'user', message: `Parcel boundary "${parcel.name}" deleted.` });
  saveDb();
  return res.json({ deleted: true, id: parcel.id });
});

export default router;
