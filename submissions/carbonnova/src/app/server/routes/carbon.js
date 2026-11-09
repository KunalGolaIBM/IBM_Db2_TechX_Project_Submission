/**
 * CarbonNova — /api/projects/:id/carbon
 * Exposes the explainable carbon estimation engine (science layer).
 * NEVER calls the AI. Every response includes formulas, assumptions,
 * uncertainty and limitations.
 */
import { Router } from 'express';
import { getDb } from '../db.js';
import { estimateCarbon, METHODOLOGY } from '../lib/carbonEngine.js';

const router = Router();

const RANGE_MS = { '24h': 24 * 3600000, '7d': 7 * 86400000, '30d': 30 * 86400000, '90d': 90 * 86400000 };

router.get('/projects/:id/carbon', (req, res) => {
  const db = getDb();
  const project = db.projects.find((p) => p.id === req.params.id && p.owner_id === String(req.query.owner || 'user-1'));
  if (!project) return res.status(404).json({ error: 'NOT_FOUND', message: 'Project not found' });

  const range = RANGE_MS[req.query.range] || RANGE_MS['7d'];
  const since = Date.now() - range;
  const readings = db.readings
    .filter((r) => r.project_id === project.id && new Date(r.recorded_at).getTime() >= since)
    .sort((a, b) => a.recorded_at.localeCompare(b.recorded_at));

  const estimate = estimateCarbon(project, readings);

  // Daily trend: re-run the same engine on each day's reading bucket so the
  // chart shows how the *estimate* evolves — deterministic, not AI.
  const buckets = new Map();
  for (const r of readings) {
    const day = r.recorded_at.slice(0, 10);
    if (!buckets.has(day)) buckets.set(day, []);
    buckets.get(day).push(r);
  }
  const trend = [...buckets.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([day, dayReadings]) => {
    const e = estimateCarbon(project, dayReadings);
    return {
      date: day,
      readings: dayReadings.length,
      net_sequestration_tCO2e_yr: e.metrics.net_sequestration_project_tCO2e_yr,
      respiration_tCO2e_yr: e.metrics.soil_respiration_project_tCO2e_yr,
      env_response: e.metrics.environmental_response_factor,
      uncertainty_low: e.metrics.net_sequestration_uncertainty.low,
      uncertainty_high: e.metrics.net_sequestration_uncertainty.high,
      avg_moisture_pct: e.inputs_used.avg_soil_moisture_pct,
      avg_respiration_mg: e.inputs_used.avg_soil_respiration_mg_m2_h,
      data_source: e.data_source,
    };
  });

  res.json({
    estimate,
    trend,
    methodology: METHODOLOGY,
    period: { range: req.query.range || '7d', readings_used: readings.length },
  });
});

export default router;
