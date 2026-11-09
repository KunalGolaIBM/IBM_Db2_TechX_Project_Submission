/**
 * CarbonNova — NVIDIA Build API integration
 * =========================================
 * Talks to the official NVIDIA Build API using an NVIDIA API key.
 *
 * Endpoint   : https://integrate.api.nvidia.com/v1/chat/completions
 * Protocol   : OpenAI-compatible chat completions
 * Auth       : NVIDIA_API_KEY env var (NEVER exposed to the frontend)
 * Models     : nvidia/Nemotron-3_5-Lightning (default, supported by NVIDIA Build accounts)
 *              Model ID is configurable via NVIDIA_MODEL env var
 *
 * This module is intentionally kept SEPARATE from lib/nebius.js:
 * scientific calculations never depend on the LLM, and the LLM never
 * fabricates numbers — it only explains data passed to it.
 *
 * Security:
 *   - NVIDIA_API_KEY is loaded from .env via dotenv
 *   - The key NEVER appears in any API response or frontend code
 *   - /api/ai/status reports only whether it is configured, never the value
 */

import OpenAI from 'openai';

// The official NVIDIA Build API endpoint
export const NVIDIA_BASE_URL = 'https://integrate.api.nvidia.com/v1';

// Model ID configurable via env; default is the Nemotron 3.5 model supported
// by most NVIDIA Build accounts. Users with a different model can override.
export const NVIDIA_MODEL =
  process.env.NVIDIA_MODEL || 'nvidia/Nemotron-3_5-LightNING';

let client = null;

export function getClient() {
  const apiKey = process.env.NVIDIA_API_KEY;
  if (!apiKey) return null;
  if (!client) {
    client = new OpenAI({ baseURL: NVIDIA_BASE_URL, apiKey });
  }
  return client;
}

/** Test/DI hook — allows injecting a stub client. */
export function setClientForTesting(c) {
  client = c;
}

export function isConfigured() {
  return Boolean(process.env.NVIDIA_API_KEY);
}

/** Normalized error taxonomy so the API can return actionable errors.
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
 * Run a chat completion against the NVIDIA Nemotron model via Build API.
 * @param {Array} messages  Array of {role, content} messages
 * @param {object} options  { temperature?, maxTokens? }
 * @returns {Promise<{content: string, model: string, usage: object}>}
 */
export async function chat(messages, { temperature = 0.3, maxTokens = 900 } = {}) {
  const c = getClient();
  if (!c) {
    throw new AiError(
      'AI_NOT_CONFIGURED',
      'NVIDIA_API_KEY is not set on the server. Add it to server/.env and restart. The AI assistant is disabled until then.',
      503
    );
  }
  try {
    const completion = await c.chat.completions.create({
      model: NVIDIA_MODEL,
      messages,
      temperature,
      max_tokens: maxTokens,
    });
    const choice = completion.choices?.[0];
    const content = choice?.message?.content;
    if (!content) {
      throw new AiError('AI_EMPTY_RESPONSE', 'The model returned an empty response. Please retry.', 502);
    }
    return { content, model: completion.model || NVIDIA_MODEL, usage: completion.usage || null };
  } catch (err) {
    if (err instanceof AiError) throw err;
    const status = err?.status ?? err?.statusCode ?? 0;
    if (status === 401 || status === 403) {
      throw new AiError('AI_AUTH_FAILED', 'NVIDIA rejected the API key (check NVIDIA_API_KEY).', 502);
    }
    if (status === 404) {
      throw new AiError(
        'AI_MODEL_NOT_FOUND',
        `Model '${NVIDIA_MODEL}' was not found. Set NVIDIA_MODEL to a model listed at build.nvidia.com/models.`,
        502
      );
    }
    if (status === 429) {
      throw new AiError('AI_RATE_LIMITED', 'NVIDIA rate limit hit. Wait a moment and retry.', 429);
    }
    if (status === 0 || err?.code === 'ECONNREFUSED' || err?.name === 'APIConnectionError') {
      throw new AiError('AI_UNREACHABLE', 'Could not reach NVIDIA Build API. Check network connectivity and retry.', 502);
    }
    throw new AiError('AI_UPSTREAM_ERROR', `NVIDIA API error: ${err?.message || 'unknown'}. Please retry.`, 502);
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