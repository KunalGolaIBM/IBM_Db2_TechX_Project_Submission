import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { generatePlans, suggestMissionFromPlan } from './aiService.ts';
import type { AIInterpretation, AIPlans, CaptureContext } from '../lib/odysseyTypes.ts';

// The edge function is unreachable, so generatePlans uses the deterministic planner
vi.mock('../lib/supabase', () => ({
  supabase: {
    functions: {
      invoke: vi.fn(async () => ({ data: null, error: { message: 'offline' } })),
    },
  },
}));

const INTERPRETATION: AIInterpretation = {
  aiGenerated: false,
  items: [
    { text: 'Write research paper', category: 'task', priority: 'medium', isConsistency: false },
    { text: 'Email the professor', category: 'task', priority: 'medium', isConsistency: false },
    { text: 'Daily DSA practice', category: 'goal', priority: 'low', isConsistency: true },
  ],
};

function capture(availableHours: number, energy: CaptureContext['energy']): CaptureContext {
  return {
    rawInput: 'write research paper, email the professor',
    availableHours,
    energy,
    consistencyGoals: ['Daily DSA practice'],
    horizon: 'today',
    capturedAt: '2026-03-10T12:00:00.000Z',
  };
}

function balanced(plans: AIPlans) {
  return plans.plans.find(p => p.id === 'balanced')!.orderedItems;
}

beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('generatePlans offline fallback', () => {
  it('passes hours and energy through to the planner', async () => {
    const stretched = await generatePlans(capture(1, 'low'), INTERPRETATION);
    const roomy = await generatePlans(capture(8, 'high'), INTERPRETATION);

    expect(stretched.aiGenerated).toBe(false);
    expect(balanced(stretched).map(i => i.text)).toEqual([
      'Email the professor',
      'Daily DSA practice',
      'Write research paper',
    ]);
    expect(balanced(roomy).map(i => i.text)).toEqual([
      'Write research paper',
      'Daily DSA practice',
      'Email the professor',
    ]);
  });

  it('carries the heavy flag into the rationale', async () => {
    const plans = await generatePlans(capture(1, 'low'), INTERPRETATION);

    expect(balanced(plans).find(i => i.text === 'Write research paper')?.rationale).toMatch(/Heavy for today/);
  });
});

describe('suggestMissionFromPlan offline fallback', () => {
  it('keeps the heavy flag out of the mission objective', async () => {
    const ctx = capture(1, 'low');
    const heavyOnly = { ...INTERPRETATION, items: INTERPRETATION.items.slice(0, 1) };
    const { plans } = await generatePlans(ctx, heavyOnly);

    expect(plans[0].orderedItems[0].rationale).toMatch(/Heavy for today/);

    const mission = await suggestMissionFromPlan(ctx, plans[0]);
    expect(mission.objective).toContain('Address after deadline-critical work.');
    expect(mission.objective).not.toMatch(/Heavy for today/);
  });
});
