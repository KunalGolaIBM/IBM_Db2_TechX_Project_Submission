import { Router } from 'express';
import { getDb, saveDb, newId, logActivity } from '../db.js';
import { estimateCarbon, METHODOLOGY } from '../lib/carbonEngine.js';

const router = Router();

router.get('/projects/:id/assessments', (req, res) => {
  const db = getDb();
  if (!db.projects.some((project) => project.id === req.params.id && project.owner_id === String(req.query.owner || 'user-1'))) {
    return res.status(404).json({ error: 'NOT_FOUND', message: 'Project not found.' });
  }
  const assessments = db.assessments.filter((assessment) => assessment.project_id === req.params.id);
  return res.json({ assessments });
});

router.post('/projects/:id/assessments', (req, res) => {
  const db = getDb();
  const project = db.projects.find((item) => item.id === req.params.id && item.owner_id === String(req.body?.owner_id || 'user-1'));
  if (!project) return res.status(404).json({ error: 'NOT_FOUND', message: 'Project not found.' });

  const readings = db.readings
    .filter((reading) => reading.project_id === project.id)
    .sort((a, b) => a.recorded_at.localeCompare(b.recorded_at))
    .slice(-500);
  const estimate = estimateCarbon(project, readings);
  const previous = db.assessments.find((assessment) => assessment.project_id === project.id);
  const now = new Date().toISOString();
  const assessment = {
    id: newId('assess'), project_id: project.id, parcel_id: db.parcels.find((parcel) => parcel.project_id === project.id)?.id || null,
    assessment_date: now, revision: previous ? previous.revision + 1 : 1, previous_assessment_id: previous?.id || null,
    data_source_references: [...new Set(readings.map((reading) => reading.data_source))],
    input_observation_ids: readings.map((reading) => reading.id),
    observations: readings.map((reading) => ({ id: reading.id, recorded_at: reading.recorded_at, data_source: reading.data_source, is_simulated: Boolean(reading.is_simulated), values: reading.values })),
    calculation_method: { name: METHODOLOGY.framework, version: METHODOLOGY.engine_version, standards_note: METHODOLOGY.standards_note },
    units: { area: 'hectares', carbon_stock: 'tC', carbon_dioxide_equivalent: 'tCO2e', flow: 'tCO2e/year' },
    assumptions: estimate.assumptions, missing_information: estimate.missing_inputs,
    uncertainty_and_quality_limitations: estimate.limitations,
    estimate, ai_interpretation: null, human_review_status: 'pending', supporting_evidence: [],
    created_at: now,
  };
  db.assessments.unshift(assessment);
  logActivity({ project_id: project.id, type: 'assessment_created', source: 'deterministic-engine', message: `Assessment ${assessment.id} revision ${assessment.revision} saved with ${readings.length} linked observations; human review pending.` });
  saveDb();
  return res.status(201).json({ assessment });
});

export default router;
