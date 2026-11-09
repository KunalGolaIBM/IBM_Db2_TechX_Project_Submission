/**
 * CarbonNova — /api/projects/:id/ai/*  (AI ASSISTANT LAYER)
 * ----------------------------------------------------------
 * Real Nebius Token Factory calls using an NVIDIA Nemotron model.
 * Every request is grounded in the project's actual data (buildUserMessage),
 * and every failure returns a structured, retryable error — the API NEVER
 * fabricates a successful AI answer.
 */
import { Router } from 'express';
import { getDb, saveDb, logActivity } from '../db.js';
import { chat, isConfigured, NEBIUS_MODEL, NEBIUS_BASE_URL, AiError, listModels } from '../lib/nebius.js';
import { prepareMessages } from '../lib/prompting.js';
import { validateQuestion } from '../lib/validate.js';

const router = Router();

const ANSWER_DISCLAIMER =
  'AI-generated explanation by an NVIDIA Nemotron model (via Nebius Token Factory), grounded in this project’s monitoring data. ' +
  'It is not a scientific calculation, not an independent verification, and not a carbon credit claim.';

function loadProjectContext(req, res) {
  const db = getDb();
  const project = db.projects.find((p) => p.id === req.params.id && p.owner_id === String(req.body?.owner_id || 'user-1'));
  if (!project) {
    res.status(404).json({ error: 'NOT_FOUND', message: 'Project not found' });
    return null;
  }
  const readings = db.readings
    .filter((r) => r.project_id === project.id)
    .sort((a, b) => a.recorded_at.localeCompare(b.recorded_at))
    .slice(-200); // keep prompt size bounded
  return { db, project, readings };
}

/** Shared handler: run a grounded completion for a given question. */
async function answer(req, res, question, { logType = 'ai_question', maxTokens = 900 } = {}) {
  const ctx = loadProjectContext(req, res);
  if (!ctx) return;
  const { db, project, readings } = ctx;

  const { messages } = prepareMessages({ project, readings, question, history: req.body.history || [] });

  try {
    const result = await chat(messages, { maxTokens });
    logActivity({
      project_id: project.id,
      type: logType,
      source: 'nebius-ai',
      message: `AI assistant answered "${question.slice(0, 80)}${question.length > 80 ? '…' : ''}" using model ${result.model}.`,
    });
    saveDb();
    res.json({
      answer: result.content,
      model: result.model,
      usage: result.usage,
      grounded: true,
      readings_context_count: readings.length,
      generated_at: new Date().toISOString(),
      disclaimer: ANSWER_DISCLAIMER,
    });
  } catch (err) {
    const aiErr = err instanceof AiError
      ? err
      : new AiError('AI_UNKNOWN_ERROR', 'Unexpected AI error. Please retry.', 500);
    logActivity({
      project_id: project.id, type: 'ai_error', source: 'nebius-ai', severity: 'warning',
      message: `AI request failed (${aiErr.code}); retryable provider error.`,
    });
    saveDb();
    res.status(aiErr.status).json({
      error: aiErr.code,
      message: aiErr.message,
      retryable: true,
      model: NEBIUS_MODEL,
      configured: isConfigured(),
    });
  }
}

// POST /api/projects/:id/ai/ask — general grounded Q&A
router.post('/projects/:id/ai/ask', async (req, res) => {
  const errors = validateQuestion(req.body);
  if (errors.length) return res.status(400).json({ error: 'VALIDATION_ERROR', details: errors });
  await answer(req, res, req.body.question.trim());
});

// Preset analysis prompts (same pipeline, curated questions)
const PRESETS = {
  summarize: 'Summarize the current monitoring status of this project in plain language: what the sensors are showing, overall trends, and what needs attention.',
  anomalies: 'Identify any unusual or out-of-range sensor readings in the available data, and explain what might cause them. If nothing looks unusual, say so clearly.',
  explain: 'Explain how the carbon estimate for this project was calculated, including the key formulas, assumptions, and uncertainty — in simple language for a non-expert.',
  limitations: 'What are the main data gaps and limitations of this project’s monitoring right now? What should be improved before MRV verification?',
  report: 'Draft an MRV monitoring report for this project with sections: Summary, Monitoring Results, Carbon Estimate & Methodology, Data Quality & Limitations, Recommended Next Steps. Clearly mark it as an AI-generated draft for human review.',
};

// POST /api/projects/:id/ai/preset — { preset: 'summarize'|'anomalies'|'explain'|'limitations'|'report' }
router.post('/projects/:id/ai/preset', async (req, res) => {
  const key = req.body?.preset;
  if (!PRESETS[key]) {
    return res.status(400).json({ error: 'VALIDATION_ERROR', details: [`preset: one of ${Object.keys(PRESETS).join(', ')}`] });
  }
  await answer(req, res, PRESETS[key], { logType: key === 'report' ? 'ai_report_draft' : 'ai_preset', maxTokens: key === 'report' ? 1400 : 700 });
});

export default router;
