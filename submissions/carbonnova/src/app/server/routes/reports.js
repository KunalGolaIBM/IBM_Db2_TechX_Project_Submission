/**
 * CarbonNova — /api/projects/:id/reports
 * Downloadable MRV reports: PDF (full report) and CSV (data exports).
 * Every report records an entry in the audit trail (db.reports + activity).
 */
import { Router } from 'express';
import { getDb, saveDb, newId, logActivity } from '../db.js';
import { buildReportPdf, buildReadingsCsv, buildEstimateCsv } from '../lib/reportGen.js';
import { estimateCarbon, METHODOLOGY } from '../lib/carbonEngine.js';
import { chat, isConfigured, AiError } from '../lib/nebius.js';
import { prepareMessages } from '../lib/prompting.js';

const router = Router();

const RANGE_MS = { '24h': 24 * 3600000, '7d': 7 * 86400000, '30d': 30 * 86400000, '90d': 90 * 86400000 };

function context(req, res) {
  const db = getDb();
  const project = db.projects.find((p) => p.id === req.params.id && p.owner_id === String(req.query.owner || req.body?.owner_id || 'user-1'));
  if (!project) {
    res.status(404).json({ error: 'NOT_FOUND', message: 'Project not found' });
    return null;
  }
  const range = RANGE_MS[req.query.range] || RANGE_MS['30d'];
  const since = Date.now() - range;
  const readings = db.readings
    .filter((r) => r.project_id === project.id && new Date(r.recorded_at).getTime() >= since)
    .sort((a, b) => a.recorded_at.localeCompare(b.recorded_at));
  const activity = db.activity.filter((a) => a.project_id === project.id);
  return { db, project, readings, activity, rangeKey: req.query.range || '30d' };
}

function registerReport(db, { project, type, readings, includesAi }) {
  const entry = {
    id: newId('rep'),
    project_id: project.id,
    type,
    generated_at: new Date().toISOString(),
    readings_count: readings.length,
    data_sources: [...new Set(readings.map((r) => r.data_source))],
    includes_ai_content: Boolean(includesAi),
    engine_version: METHODOLOGY.engine_version,
  };
  db.reports.unshift(entry);
  if (db.reports.length > 200) db.reports.length = 200;
  return entry;
}

// GET /api/projects/:id/reports — report audit history
router.get('/projects/:id/reports', (req, res) => {
  const db = getDb();
  const project = db.projects.find((item) => item.id === req.params.id && item.owner_id === String(req.query.owner || 'user-1'));
  if (!project) return res.status(404).json({ error: 'NOT_FOUND', message: 'Project not found.' });
  const reports = db.reports.filter((r) => r.project_id === req.params.id);
  res.json({ reports });
});

// POST /api/projects/:id/reports/pdf  body: { include_ai_summary?: boolean }
router.post('/projects/:id/reports/pdf', async (req, res) => {
  const ctx = context(req, res);
  if (!ctx) return;
  const { db, project, readings, activity } = ctx;
  const includeAi = Boolean(req.body?.include_ai_summary);

  let aiSummary = null;
  let aiError = null;
  if (includeAi) {
    if (!isConfigured()) {
      aiError = 'NEBIUS_API_KEY not configured — AI summary omitted from this report.';
    } else {
      try {
        const { messages } = prepareMessages({
          project, readings,
          question: 'Draft the narrative summary section of an MRV monitoring report: monitoring status, key trends, carbon estimate highlights, data quality and next steps. Mark it clearly as an AI-generated draft.',
        });
        const result = await chat(messages, { maxTokens: 1100 });
        aiSummary = result.content;
      } catch (err) {
        aiError = err instanceof AiError ? err.message : 'AI summary unavailable (unexpected error).';
      }
    }
  }

  try {
    const pdf = await buildReportPdf({ project, readings, activity, aiSummary });
    const report = registerReport(db, {
      project, type: 'pdf', readings, includesAi: Boolean(aiSummary),
    });
    logActivity({
      project_id: project.id, type: 'report_generated', source: 'system',
      message: `MRV PDF report generated (${readings.length} readings${aiSummary ? ', with AI summary draft' : ''}). Report ${report.id}.`,
    });
    saveDb();

    const stamp = new Date().toISOString().slice(0, 10);
    const safeName = project.name.replace(/[^a-z0-9]+/gi, '-').toLowerCase();
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', `attachment; filename="carbonnova-mrv-${safeName}-${stamp}.pdf"`);
    res.setHeader('X-Report-Id', report.id);
    if (aiError) res.setHeader('X-Ai-Summary-Error', encodeURIComponent(aiError));
    res.send(pdf);
  } catch (err) {
    console.error('[reports] PDF generation failed:', err);
    res.status(500).json({ error: 'REPORT_GENERATION_FAILED', message: err.message, retryable: true });
  }
});

// POST /api/projects/:id/reports/csv  body: { kind: 'readings'|'carbon' }
router.post('/projects/:id/reports/csv', (req, res) => {
  const ctx = context(req, res);
  if (!ctx) return;
  const { db, project, readings } = ctx;
  const kind = req.body?.kind === 'carbon' ? 'carbon' : 'readings';

  const csv = kind === 'carbon'
    ? buildEstimateCsv(project, readings)
    : buildReadingsCsv(project, readings);

  const report = registerReport(db, { project, type: `csv_${kind}`, readings, includesAi: false });
  logActivity({
    project_id: project.id, type: 'report_generated', source: 'system',
    message: `${kind === 'carbon' ? 'Carbon estimate' : 'Readings'} CSV export generated (${readings.length} rows). Report ${report.id}.`,
  });
  saveDb();

  const stamp = new Date().toISOString().slice(0, 10);
  const safeName = project.name.replace(/[^a-z0-9]+/gi, '-').toLowerCase();
  res.setHeader('Content-Type', 'text/csv; charset=utf-8');
  res.setHeader('Content-Disposition', `attachment; filename="carbonnova-${kind}-${safeName}-${stamp}.csv"`);
  res.setHeader('X-Report-Id', report.id);
  res.send(csv);
});

export default router;
