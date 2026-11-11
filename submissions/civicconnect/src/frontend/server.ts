import express, { Request, Response } from 'express';
import { createServer as createViteServer } from 'vite';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3000;

app.use(express.json({ limit: '10mb' }));

// 7 Civic categories and their recommended departments
const CATEGORY_DEPARTMENT_MAP: Record<string, string> = {
  'Garbage Collection': 'Sanitation Department',
  'Road Damage / Potholes': 'Public Works Department',
  'Streetlight Problems': 'Electricity Department',
  'Water Leakage': 'Water Supply Department',
  'Drainage and Sewage': 'Drainage Department',
  'Public Property Damage': 'Public Works Department',
  'Other Civic Issues': 'Municipal Administration'
};

/**
 * AI-Assisted Complaint Classifier endpoint
 * Proxies to the Python FastAPI backend (IBM Db2 + LangChain).
 * Falls back to heuristic classification if the backend is unavailable.
 */
app.post('/api/ai/classify', async (req: Request, res: Response) => {
  const { title = '', description = '' } = req.body;

  if (!title && !description) {
    res.status(400).json({ error: 'Title or description is required for classification' });
    return;
  }

  // Proxy to Python FastAPI backend (IBM Db2 + LangChain + watsonx.ai)
  const backendUrl = process.env.BACKEND_API_URL || 'http://localhost:8000';
  try {
    const upstream = await fetch(`${backendUrl}/api/ai/classify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, description }),
      signal: AbortSignal.timeout(5000),
    });
    if (upstream.ok) {
      const data = await upstream.json();
      res.json(data);
      return;
    }
  } catch {
    // Backend unavailable — fall through to heuristic
  }

  // Heuristic fallback (no external dependency)
  const text = `${title} ${description}`.toLowerCase();
  let category = 'Other Civic Issues';
  let priority: 'low' | 'medium' | 'high' | 'urgent' = 'medium';

  if (text.match(/pothole|road|crater|asphalt|tar|speedbreaker|highway|sidewalk|pavement/)) {
    category = 'Road Damage / Potholes';
    priority = text.match(/deep|huge|accident|deadly|severe|tire|crash/) ? 'high' : 'medium';
  } else if (text.match(/garbage|trash|waste|dump|rubbish|litter|bins|smell|stench|sanitation/)) {
    category = 'Garbage Collection';
    priority = text.match(/overflow|disease|hospital|school|rotting/) ? 'high' : 'medium';
  } else if (text.match(/light|streetlight|lamp|dark|pole|wire|spark|blackout|electric/)) {
    category = 'Streetlight Problems';
    priority = text.match(/spark|exposed|shock|fire|hazard/) ? 'urgent' : 'low';
  } else if (text.match(/water|pipe|leak|burst|flow|pressure|meter|tap/)) {
    category = 'Water Leakage';
    priority = text.match(/burst|flooding|gushing|waste/) ? 'high' : 'medium';
  } else if (text.match(/drain|sewage|gutter|manhole|stagnant|overflowing drain|clogged/)) {
    category = 'Drainage and Sewage';
    priority = text.match(/overflow|manhole open|choked|monsoon/) ? 'urgent' : 'high';
  } else if (text.match(/park|bench|bus stop|shelter|sign|statue|fence|wall|public property/)) {
    category = 'Public Property Damage';
    priority = 'low';
  }

  const department = CATEGORY_DEPARTMENT_MAP[category] || 'Municipal Administration';
  const words = text.replace(/[^a-zA-Z0-9\s]/g, '').split(/\s+/).filter(w => w.length > 4);
  const keywords = Array.from(new Set(words)).slice(0, 5);

  res.json({
    category,
    department,
    priority,
    keywords: keywords.length > 0 ? keywords : ['civic', 'infrastructure', 'maintenance'],
    summary: `Citizen reported ${category.toLowerCase()} at the specified locality requiring inspection by ${department}.`,
    aiPowered: false
  });
});

/**
 * Health check endpoint
 */
app.get('/api/health', (_req: Request, res: Response) => {
  res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

// Setup Vite middleware in dev or serve static files in production
async function startServer() {
  const isProd = process.env.NODE_ENV === 'production';

  if (!isProd) {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    app.use(express.static(path.resolve(__dirname, 'dist')));
    app.get('*', (_req: Request, res: Response) => {
      res.sendFile(path.resolve(__dirname, 'dist', 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`CivicConnect server running on http://0.0.0.0:${PORT}`);
  });
}

startServer().catch((err) => {
  console.error('Failed to start server:', err);
  process.exit(1);
});
