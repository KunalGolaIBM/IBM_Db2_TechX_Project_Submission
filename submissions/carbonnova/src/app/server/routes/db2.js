import { Router } from 'express';
import { healthCheck, isDb2Configured } from '../lib/db2.js';
import { initDb2Schema } from '../lib/db2Schema.js';

const router = Router();

router.get('/health/db2', async (req, res) => {
  try {
    const result = await healthCheck();
    res.status(result.ok ? 200 : 503).json(result);
  } catch (e) {
    res.status(503).json({ ok: false, configured: isDb2Configured(), error: String(e && e.message || e) });
  }
});

router.post('/db2/init', async (req, res) => {
  try {
    if (!isDb2Configured()) return res.status(503).json({ ok: false, error: 'IBM Db2 is not configured.' });
    const result = await initDb2Schema();
    res.status(result.ok ? 200 : 500).json(result);
  } catch (e) {
    res.status(500).json({ ok: false, error: String(e && e.message || e) });
  }
});

router.get('/db2/status', (req, res) => {
  res.json({ configured: isDb2Configured(), database: process.env.DB2_DATABASE || null, host: process.env.DB2_HOST || null, port: process.env.DB2_PORT || null, note: 'Set DB2_* variables and run POST /api/db2/init after Db2 is available.' });
});

export default router;
