/**
 * CarbonNova backend — Express API server
 * ========================================
 * Endpoints:
 *   GET  /api/health                 service + AI configuration status
 *   GET  /api/ai/status              Nebius/model status (never exposes the key)
 *   GET  /api/activity               platform audit/activity trail
 *   GET  /api/projects               list monitoring projects (+ summaries)
 *   POST /api/projects               create a project (validated)
 *   GET  /api/projects/:id           project detail + activity
 *   PATCH/DELETE /api/projects/:id   update / delete
 *   GET  /api/projects/:id/readings  filtered sensor series (range/limit/metric)
 *   GET  /api/projects/:id/devices   project sensor nodes
 *   GET  /api/devices                all sensor nodes
 *   POST /api/ingest                 ESP32-style physical sensor ingest (real data)
 *   GET  /api/projects/:id/carbon    explainable carbon estimate (science layer)
 *   POST /api/projects/:id/ai/ask    Nebius/Nemotron grounded Q&A
 *   POST /api/projects/:id/ai/preset curated AI prompts (summary/anomalies/…)
 *   GET/POST /api/projects/:id/reports  report audit list / PDF / CSV generation
 *
 * Security: NEBIUS_API_KEY stays in server/.env; /api/ai/status reports only
 * whether it is configured, never the value.
 */
import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.join(__dirname, '.env') });
dotenv.config(); // also honour a project-root .env if present

import { getDb, saveDb } from './db.js';
import { seedDemoData } from './seed.js';
import { isConfigured, NEBIUS_MODEL, NEBIUS_BASE_URL, listModels } from './lib/nebius.js';

import projectsRouter from './routes/projects.js';
import readingsRouter from './routes/readings.js';
import carbonRouter from './routes/carbon.js';
import aiRouter from './routes/ai.js';
import aiNvidiaRouter from './routes/ai-nvidia.js';
import reportsRouter from './routes/reports.js';
import parcelsRouter from './routes/parcels.js';
import assessmentsRouter from './routes/assessments.js';
import platformRouter from './routes/platform.js';
import db2Router from './routes/db2.js';

// NVIDIA Build AI status — safe: never returns the API key
import { isConfigured as isNvidiaConfigured, NVIDIA_BASE_URL, NVIDIA_MODEL } from './lib/nvidia.js';

export function createApp() {
  const app = express();

  app.use(cors({
    origin: process.env.CORS_ORIGIN ? process.env.CORS_ORIGIN.split(',') : true,
  }));
  app.use(express.json({ limit: '256kb' }));

  // Request log (method, url, status, ms)
  app.use((req, res, next) => {
    const start = Date.now();
    res.on('finish', () => {
      if (process.env.NODE_ENV !== 'test') {
        console.log(`${req.method} ${req.originalUrl} → ${res.statusCode} (${Date.now() - start}ms)`);
      }
    });
    next();
  });

  app.get('/api/health', async (req, res) => {
    const db = getDb();
    let db2 = { configured: false };
    try { const { isDb2Configured } = await import('./lib/db2.js'); db2.configured = isDb2Configured(); } catch {}
    res.json({
      ok: true,
      service: 'carbonnova-api',
      time: new Date().toISOString(),
      stats: {
        projects: db.projects.length,
        devices: db.devices.length,
        readings: db.readings.length,
        activity_events: db.activity.length,
        reports: db.reports.length,
      },
      ai: { configured: isConfigured(), model: NEBIUS_MODEL, nvidia_configured: isNvidiaConfigured(), nvidia_model: NVIDIA_MODEL },
      db2,
    });
  });

  // NVIDIA Build AI/provider status — safe: never returns the API key itself
  app.get('/api/ai/nvidia/status', async (req, res) => {
    const models = isNvidiaConfigured() ? await listModels() : null;
    res.json({
      configured: isNvidiaConfigured(),
      provider: 'NVIDIA Build',
      base_url: NVIDIA_BASE_URL,
      model: NVIDIA_MODEL,
      model_available: models === null ? null : models.includes(NVIDIA_MODEL),
      models_count: models?.length ?? 0,
    });
  });

  // AI/provider status — safe: never returns the API key itself
  app.get('/api/ai/status', async (req, res) => {
    const models = isConfigured() ? await listModels() : null;
    res.json({
      configured: isConfigured(),
      provider: 'Nebius Token Factory',
      base_url: NEBIUS_BASE_URL,
      model: NEBIUS_MODEL,
      model_available: models === null ? null : models.includes(NEBIUS_MODEL),
      models_count: models?.length ?? 0,
    });
  });

  app.get('/api/activity', (req, res) => {
    const db = getDb();
    const limit = Math.min(Number(req.query.limit) || 50, 500);
    res.json({ activity: db.activity.slice(0, limit) });
  });

  app.use('/api', projectsRouter);
  app.use('/api', readingsRouter);
  app.use('/api', carbonRouter);
  app.use('/api', aiRouter);
  app.use('/api', aiNvidiaRouter);
  app.use('/api', reportsRouter);
  app.use('/api', parcelsRouter);
  app.use('/api', assessmentsRouter);
  app.use('/api', platformRouter);
  app.use('/api', db2Router);

  app.use('/api', (req, res) => {
    res.status(404).json({ error: 'NOT_FOUND', message: `No API route for ${req.method} ${req.originalUrl}` });
  });

  // Central error handler — structured JSON, no stack leaks to clients
  app.use((err, req, res, next) => {
    if (err?.type === 'entity.parse.failed') {
      return res.status(400).json({ error: 'INVALID_JSON', message: 'Request body is not valid JSON.' });
    }
    if (err?.type === 'entity.too.large') {
      return res.status(413).json({ error: 'PAYLOAD_TOO_LARGE', message: 'Request body exceeds 256KB.' });
    }
    console.error('[api] Unhandled error:', err);
    res.status(500).json({ error: 'INTERNAL_ERROR', message: 'Unexpected server error.', retryable: true });
  });

  return app;
}


export function startServer(port = process.env.PORT || 4000) {
  if (process.env.CARBONNOVA_NO_SEED !== '1') seedDemoData();
  const app = createApp();
  return new Promise((resolve) => {
    const server = app.listen(port, () => {
      console.log(`CarbonNova API listening on http://localhost:${port}`);
      console.log(`  AI: Nebius configured=${isConfigured()}, NVIDIA configured=${isNvidiaConfigured()} (model: ${NEBIUS_MODEL} / ${NVIDIA_MODEL})`);
      resolve(server);
    });
  });
}

// Run when executed directly (node index.js / npm start) — not when imported by tests
const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  startServer().then(() => saveDb());
}
