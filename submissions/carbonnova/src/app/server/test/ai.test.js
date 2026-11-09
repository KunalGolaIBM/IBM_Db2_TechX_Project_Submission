/** Unit tests — Nebius client wrapper + prompt grounding (stubbed provider). Run: npm test */
import { test, describe, before, afterEach } from 'node:test';
import assert from 'node:assert/strict';

process.env.NEBIUS_API_KEY = 'test-key-not-real';
process.env.NODE_ENV = 'test';

const nebius = await import('../lib/nebius.js');
const prompting = await import('../lib/prompting.js');

const PROJECT = {
  id: 'proj-sahyadri', name: 'Sahyadri Agroforestry Reserve', land_type: 'agroforestry',
  area_acres: 450, location: 'Pune, Maharashtra', status: 'active',
  description: 'Mixed agroforestry.', created_at: '2025-11-15T00:00:00Z',
};

const readings = Array.from({ length: 10 }, (_, i) => ({
  recorded_at: new Date(Date.now() - (10 - i) * 3600000).toISOString(),
  data_source: 'simulated', is_simulated: true,
  values: { soil_moisture_pct: 44, soil_temp_c: 25, soil_co2_respiration: 300, soil_ph: 6.5, ec_ds_m: 0.8, air_temp_c: 28, air_humidity_pct: 60 },
}));

function stubClient(handler) {
  return { chat: { completions: { create: handler } }, models: { list: async () => ({ data: [] }) } };
}

const okCompletion = (content) => ({
  choices: [{ message: { content } }],
  model: 'nvidia/Nemotron-3_5-Lightning',
  usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
});

afterEach(() => nebius.setClientForTesting(null));

describe('Nebius client', () => {
  test('unconfigured → AI_NOT_CONFIGURED (503), never a fake answer', async () => {
    const key = process.env.NEBIUS_API_KEY;
    delete process.env.NEBIUS_API_KEY;
    await assert.rejects(
      () => nebius.chat([{ role: 'user', content: 'hi' }]),
      (err) => err.code === 'AI_NOT_CONFIGURED' && err.status === 503 && /NEBIUS_API_KEY/.test(err.message)
    );
    process.env.NEBIUS_API_KEY = key;
  });

  test('uses verified default endpoint + Nemotron model', () => {
    assert.equal(nebius.NEBIUS_BASE_URL, 'https://api.tokenfactory.nebius.com/v1/');
    assert.match(nebius.NEBIUS_MODEL, /^nvidia\/Nemotron/i);
  });

  test('successful completion returns content, model and usage', async () => {
    nebius.setClientForTesting(stubClient(async () => okCompletion('Grounded answer.')));
    const r = await nebius.chat([{ role: 'user', content: 'q' }]);
    assert.equal(r.content, 'Grounded answer.');
    assert.match(r.model, /Nemotron/i);
    assert.equal(r.usage.total_tokens, 15);
  });

  test('sends our messages to the Nemotron model', async () => {
    let captured;
    nebius.setClientForTesting(stubClient(async (params) => { captured = params; return okCompletion('ok'); }));
    await nebius.chat([{ role: 'system', content: 's' }, { role: 'user', content: 'q' }]);
    assert.equal(captured.model, nebius.NEBIUS_MODEL);
    assert.equal(captured.messages.length, 2);
  });

  test('401 → AI_AUTH_FAILED', async () => {
    nebius.setClientForTesting(stubClient(async () => { const e = new Error('unauthorized'); e.status = 401; throw e; }));
    await assert.rejects(() => nebius.chat([]), (e) => e.code === 'AI_AUTH_FAILED');
  });

  test('404 → AI_MODEL_NOT_FOUND with fix hint', async () => {
    nebius.setClientForTesting(stubClient(async () => { const e = new Error('no model'); e.status = 404; throw e; }));
    await assert.rejects(() => nebius.chat([]), (e) => e.code === 'AI_MODEL_NOT_FOUND' && /tokenfactory.nebius.com\/models/.test(e.message));
  });

  test('429 → AI_RATE_LIMITED (429) and connection error → AI_UNREACHABLE', async () => {
    nebius.setClientForTesting(stubClient(async () => { const e = new Error('slow down'); e.status = 429; throw e; }));
    await assert.rejects(() => nebius.chat([]), (e) => e.code === 'AI_RATE_LIMITED' && e.status === 429);

    nebius.setClientForTesting(stubClient(async () => { throw Object.assign(new Error('fetch failed'), { code: 'ECONNREFUSED' }); }));
    await assert.rejects(() => nebius.chat([]), (e) => e.code === 'AI_UNREACHABLE' && e.status === 502);
  });

  test('empty model response → AI_EMPTY_RESPONSE (no fabrication)', async () => {
    nebius.setClientForTesting(stubClient(async () => ({ choices: [{ message: { content: '' } }] })));
    await assert.rejects(() => nebius.chat([]), (e) => e.code === 'AI_EMPTY_RESPONSE');
  });
});

describe('prompt grounding', () => {
  test('system prompt enforces missing-data honesty and AI-vs-verification distinction', () => {
    const sys = prompting.systemPrompt();
    assert.match(sys, /Never invent numbers/i);
    assert.match(sys, /what is missing/i);
    assert.match(sys, /NOT a verification body/i);
    assert.match(sys, /SIMULATED/);
    assert.match(sys, /NOT verified carbon credits/i);
  });

  test('user message embeds real project data + engine output', () => {
    const { messages, estimate } = prompting.prepareMessages({
      project: PROJECT, readings, question: 'How is my soil doing?',
    });
    assert.equal(messages[0].role, 'system');
    const user = messages[messages.length - 1].content;
    assert.match(user, /Sahyadri Agroforestry Reserve/);
    assert.match(user, /450 acres/);
    assert.match(user, /SIMULATED demo sensor data/);
    assert.match(user, /CARBON ESTIMATION ENGINE OUTPUT/);
    assert.match(user, /How is my soil doing\?/);
    // engine numbers appear, proving answers are grounded, not invented
    assert.ok(user.includes(String(estimate.metrics.soc_stock_total_tC)));
  });

  test('empty readings → prompt says data is missing instead of hiding it', () => {
    const { messages } = prompting.prepareMessages({ project: PROJECT, readings: [], question: 'Trend?' });
    const user = messages[messages.length - 1].content;
    assert.match(user, /No sensor readings are available/);
  });

  test('history is trimmed and role-filtered', () => {
    const { messages } = prompting.prepareMessages({
      project: PROJECT, readings, question: 'Q2',
      history: [
        { role: 'user', content: 'Q1' }, { role: 'assistant', content: 'A1' },
        { role: 'tool', content: 'SHOULD_NOT_APPEAR' },
        ...Array.from({ length: 10 }, (_, i) => ({ role: 'user', content: `old ${i}` })),
      ],
    });
    const roles = messages.map((m) => m.role);
    assert.deepEqual(roles.slice(0, 1), ['system']);
    assert.ok(!messages.some((m) => m.content?.includes('SHOULD_NOT_APPEAR')));
    assert.ok(messages.length <= 6, `messages should be trimmed, got ${messages.length}`);
  });
});
