/**
 * CarbonNova — Nebius Token Factory integration (AI LAYER)
 * ========================================================
 * Talks to Nebius Token Factory's OpenAI-compatible API using an
 * NVIDIA Nemotron open-source model.
 *
 * Verified integration details (docs.tokenfactory.nebius.com, token-factory-cookbook):
 *   - Base URL : https://api.tokenfactory.nebius.com/v1/
 *   - Protocol : OpenAI-compatible chat completions
 *   - Auth     : NEBIUS_API_KEY env var (NEVER exposed to the frontend)
 *   - Model    : nvidia/Nemotron-3_5-Lightning (default; Nebius documents
 *                it as the recommended replacement for several deprecated
 *                serverless models in its Aug 2026 migration notice).
 *                Configure via NEBIUS_MODEL; availability is checked
 *                best-effort at /api/ai/status via /models endpoint.
 *
 * This module is intentionally kept SEPARATE from lib/carbonEngine.js:
 * scientific calculations never depend on the LLM, and the LLM never
 * fabricates numbers — it only explains data passed to it.
 */
import OpenAI from 'openai';

export const NEBIUS_BASE_URL =
  process.env.NEBIUS_BASE_URL || 'https://api.tokenfactory.nebius.com/v1/';
export const NEBIUS_MODEL =
  process.env.NEBIUS_MODEL || 'nvidia/Nemotron-3_5-Lightning';
const REQUEST_TIMEOUT_MS = Math.max(1000, Number(process.env.NEBIUS_TIMEOUT_MS) || 30000);

let client = null;

export function getClient() {
  const apiKey = process.env.NEBIUS_API_KEY;
  if (!apiKey) return null;
  if (!client) {
    client = new OpenAI({ baseURL: NEBIUS_BASE_URL, apiKey, timeout: REQUEST_TIMEOUT_MS, maxRetries: 1 });
  }
  return client;
}

/** Test/DI hook — allows injecting a stub client. */
export function setClientForTesting(c) {
  client = c;
}

export function isConfigured() {
  return Boolean(process.env.NEBIUS_API_KEY);
}

export function resetClientForTesting() {
  client = null;
}

/**
 * Normalized error taxonomy so the API can return actionable errors.
 * The frontend shows a clear message + retry button; we NEVER fake a reply.
 */
export class AiError extends Error {
  constructor(code, message, status = 502) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

/**
 * Run a chat completion against the Nemotron model.
 * @returns {Promise<{content: string, model: string, usage: object}>}
 */
export async function chat(messages, { temperature = 0.3, maxTokens = 900 } = {}) {
  const c = getClient();
  if (!c) {
    throw new AiError(
      'AI_NOT_CONFIGURED',
      'NEBIUS_API_KEY is not set on the server. Add it to server/.env and restart. The AI assistant is disabled until then.',
      503
    );
  }
  try {
    const completion = await c.chat.completions.create({
      model: NEBIUS_MODEL,
      messages,
      temperature,
      max_tokens: maxTokens,
    });
    const choice = completion.choices?.[0];
    const content = choice?.message?.content;
    if (!content) {
      throw new AiError('AI_EMPTY_RESPONSE', 'The model returned an empty response. Please retry.', 502);
    }
    return { content, model: completion.model || NEBIUS_MODEL, usage: completion.usage || null };
  } catch (err) {
    if (err instanceof AiError) throw err;
    const status = err?.status ?? 0;
    if (status === 401 || status === 403) {
      throw new AiError('AI_AUTH_FAILED', 'Nebius rejected the API key (check NEBIUS_API_KEY).', 502);
    }
    if (status === 404) {
      throw new AiError(
        'AI_MODEL_NOT_FOUND',
        `Model '${NEBIUS_MODEL}' was not found on this Nebius project. Set NEBIUS_MODEL to a model listed at tokenfactory.nebius.com/models.`,
        502
      );
    }
    if (status === 429) {
      throw new AiError('AI_RATE_LIMITED', 'Nebius rate limit hit. Wait a moment and retry.', 429);
    }
    if (status === 408 || err?.name === 'APIConnectionTimeoutError' || err?.code === 'ETIMEDOUT') {
      throw new AiError('AI_TIMEOUT', 'Nebius inference timed out. Please retry shortly.', 504);
    }
    if (status === 0 || err?.code === 'ECONNREFUSED' || err?.name === 'APIConnectionError') {
      throw new AiError('AI_UNREACHABLE', 'Could not reach Nebius Token Factory. Check network connectivity and retry.', 502);
    }
    console.warn(`[nebius] inference failed code=${err?.code || 'unknown'} status=${status || 'unknown'}`);
    throw new AiError('AI_UPSTREAM_ERROR', 'Nebius inference failed. Check server configuration and retry.', 502);
  }
}

/** Check model availability against the provider's /models list (best effort). */
export async function listModels() {
  const c = getClient();
  if (!c) return null;
  try {
    const res = await c.models.list();
    return (res.data || []).map((m) => m.id);
  } catch {
    return null; // best effort — endpoint is not critical path
  }
}
