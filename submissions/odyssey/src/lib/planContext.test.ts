import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { buildApproaches, type ApproachId, type PlanApproach } from './planner.ts';
import { capacity, contextNote, contextPenalty, itemEffort, type PlanningContext } from './planContext.ts';
import { interpret, type InterpretedItem } from './interpreter.ts';
import type { EnergyLevel } from './odysseyTypes.ts';

const NOW = new Date('2026-03-10T12:00:00.000Z');
const HOURS = [0.5, 1, 2, 3, 4, 6, 8, 12];
const ENERGIES: EnergyLevel[] = ['low', 'medium', 'high'];
const APPROACHES: ApproachId[] = ['deadline', 'balanced', 'consistency'];
const COMBOS = HOURS.flatMap(availableHours => ENERGIES.map(energy => ({ availableHours, energy })));

function dueIn(days: number, text: string, overrides: Partial<InterpretedItem> = {}): InterpretedItem {
  const deadlineDate = new Date(NOW.getTime() + days * 24 * 60 * 60 * 1000);
  return {
    text,
    category: 'deadline',
    deadlineLabel: `in ${days} days`,
    deadlineDate,
    priority: 'medium',
    isoDeadline: deadlineDate.toISOString(),
    ...overrides,
  };
}

function task(text: string, overrides: Partial<InterpretedItem> = {}): InterpretedItem {
  return { text, category: 'task', priority: 'medium', ...overrides };
}

const HEAVY = task('Write research paper');
const STANDARD = task('Sort out class notes');
const LIGHT = task('Email the professor');
const ROUTINE = task('Daily DSA practice', { category: 'goal', priority: 'low' });

function plan(items: InterpretedItem[], context?: PlanningContext) {
  return buildApproaches(items, NOW, context);
}

function order(approaches: PlanApproach[], id: ApproachId) {
  return approaches.find(a => a.id === id)!.items.map(a => a.item.text);
}

function ahead(texts: string[], first: InterpretedItem, second: InterpretedItem) {
  return texts.indexOf(first.text) < texts.indexOf(second.text);
}

// The planner reads the clock for the deadline bonus
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('itemEffort', () => {
  it.each([
    ['Write research paper', 'heavy'],
    ['Prepare for physics exam', 'heavy'],
    ['Finish math assignment', 'heavy'],
    ['Implement login page', 'heavy'],
    ['Email the professor', 'light'],
    ['Pay electricity bill', 'light'],
    ['Book dentist appointment', 'light'],
    ['Pick up the parcel', 'light'],
    ['Email the report to my guide', 'light'],
    ['Sort out class notes', 'standard'],
  ])('reads "%s" as %s', (text, effort) => {
    expect(itemEffort(task(text))).toBe(effort);
  });

  it('treats goals as routines whatever they say', () => {
    expect(itemEffort(task('Keep working on my thesis', { category: 'goal' }))).toBe('routine');
  });

  it('treats a named consistency goal as a routine even if it was read as a task', () => {
    const item = task('Write morning pages');
    expect(itemEffort(item)).toBe('heavy');
    expect(itemEffort(item, ['  write MORNING pages '])).toBe('routine');
  });
});

describe('capacity', () => {
  it.each([
    [{}, 0],
    [{ availableHours: 4, energy: 'medium' }, 0],
    [{ availableHours: 2 }, -1],
    [{ availableHours: 0.5 }, -1.75],
    [{ availableHours: 6 }, 1],
    [{ availableHours: 12 }, 1.5],
    [{ energy: 'low' }, -2],
    [{ energy: 'high' }, 1],
    [{ availableHours: 1, energy: 'low' }, -3.5],
    [{ availableHours: 1, energy: 'high' }, -0.5],
    [{ availableHours: 8, energy: 'low' }, -0.5],
    [{ availableHours: 8, energy: 'high' }, 2.5],
  ] as Array<[PlanningContext, number]>)('%o gives %d', (context, expected) => {
    expect(capacity(context)).toBe(expected);
  });

  it('never goes down when hours or energy go up', () => {
    for (const energy of ENERGIES) {
      const rooms = HOURS.map(availableHours => capacity({ availableHours, energy }));
      expect(rooms).toEqual([...rooms].sort((a, b) => a - b));
    }
    for (const availableHours of HOURS) {
      const rooms = ENERGIES.map(energy => capacity({ availableHours, energy }));
      expect(rooms).toEqual([...rooms].sort((a, b) => a - b));
    }
  });
});

describe('buildApproaches with context', () => {
  const ITEMS = [HEAVY, STANDARD, LIGHT, ROUTINE];

  it('leaves the plan alone with no context, an empty one or the Capture defaults', () => {
    const noContext = plan(ITEMS);

    expect(plan(ITEMS, {})).toEqual(noContext);
    expect(plan(ITEMS, { availableHours: 4, energy: 'medium' })).toEqual(noContext);
  });

  // Balanced gives all three tasks 6 and the goal 4 before any context
  it.each([
    { hours: 4, energy: 'medium', expected: [HEAVY, STANDARD, LIGHT, ROUTINE] },
    { hours: 2, energy: 'medium', expected: [LIGHT, STANDARD, HEAVY, ROUTINE] },
    { hours: 1, energy: 'medium', expected: [LIGHT, STANDARD, HEAVY, ROUTINE] },
    { hours: 4, energy: 'low', expected: [LIGHT, STANDARD, HEAVY, ROUTINE] },
    { hours: 2, energy: 'low', expected: [LIGHT, STANDARD, ROUTINE, HEAVY] },
    { hours: 1, energy: 'low', expected: [LIGHT, STANDARD, ROUTINE, HEAVY] },
    { hours: 1, energy: 'high', expected: [LIGHT, STANDARD, HEAVY, ROUTINE] },
    { hours: 8, energy: 'medium', expected: [HEAVY, STANDARD, LIGHT, ROUTINE] },
    { hours: 4, energy: 'high', expected: [HEAVY, STANDARD, LIGHT, ROUTINE] },
    { hours: 8, energy: 'high', expected: [HEAVY, STANDARD, ROUTINE, LIGHT] },
    { hours: 8, energy: 'low', expected: [LIGHT, STANDARD, HEAVY, ROUTINE] },
  ] as Array<{ hours: number; energy: EnergyLevel; expected: InterpretedItem[] }>)(
    'orders Balanced for $hours hours at $energy energy',
    ({ hours, energy, expected }) => {
      const approaches = plan(ITEMS, { availableHours: hours, energy });
      expect(order(approaches, 'balanced')).toEqual(expected.map(i => i.text));
    },
  );

  it('sinks heavy work further the less time there is', () => {
    const items = [task('Build portfolio site'), task('Tidy the notes folder'), ROUTINE];
    const heavyScore = (hours: number) =>
      plan(items, { availableHours: hours }).find(a => a.id === 'balanced')!.items
        .find(a => a.item.text === 'Build portfolio site')!.emphasis;

    expect(heavyScore(4)).toBeGreaterThan(heavyScore(2));
    expect(heavyScore(2)).toBeGreaterThan(heavyScore(0.5));
  });

  it('works with only hours or only energy', () => {
    const noContext = order(plan(ITEMS), 'balanced');

    expect(order(plan(ITEMS, { availableHours: 1 }), 'balanced')).not.toEqual(noContext);
    expect(order(plan(ITEMS, { energy: 'low' }), 'balanced')).not.toEqual(noContext);
  });

  it('takes a full CaptureContext', () => {
    const context = {
      rawInput: 'write research paper, email the professor',
      availableHours: 1,
      energy: 'low' as const,
      consistencyGoals: ['Daily DSA practice'],
      horizon: 'today' as const,
      capturedAt: NOW.toISOString(),
    };

    expect(order(plan(ITEMS, context), 'balanced')[0]).toBe(LIGHT.text);
  });

  it('does not penalise a named consistency goal that reads like heavy work', () => {
    const pages = task('Write morning pages');
    const context = { availableHours: 1, energy: 'low' as const };

    expect(ahead(order(plan([pages, STANDARD], context), 'balanced'), STANDARD, pages)).toBe(true);
    expect(ahead(order(plan([pages, STANDARD], { ...context, consistencyGoals: [pages.text] }), 'balanced'), pages, STANDARD)).toBe(true);
  });

  it('gives the same answer every time and leaves the input alone', () => {
    const items = [...ITEMS];
    const context = { availableHours: 2, energy: 'low' as const };
    const first = plan(items, context);

    expect(plan(items, context)).toEqual(first);
    expect(items).toEqual(ITEMS);
  });
});

describe('urgent work stays protected', () => {
  const DUE_TODAY = dueIn(0.25, 'Finish the lab report');
  const DUE_TOMORROW = dueIn(1.5, 'Submit the project proposal');
  const DUE_IN_THREE = dueIn(3, 'Build the demo for review');
  const URGENT = task('Prepare slides for the demo', { priority: 'urgent' });
  const PROTECTED = [DUE_TODAY, DUE_TOMORROW, DUE_IN_THREE, URGENT];
  const ITEMS = [HEAVY, STANDARD, LIGHT, ROUTINE, dueIn(9, 'Plan the trip'), ...PROTECTED];

  it.each(COMBOS)('nothing passes a protected item at $availableHours hours, $energy energy', context => {
    const baseline = plan(ITEMS);
    const approaches = plan(ITEMS, context);

    for (const id of APPROACHES) {
      const before = order(baseline, id);
      const after = order(approaches, id);
      for (const guarded of PROTECTED) {
        const behindBefore = before.slice(before.indexOf(guarded.text) + 1).filter(t => !PROTECTED.some(p => p.text === t));
        const behindAfter = after.slice(after.indexOf(guarded.text) + 1);
        expect(behindAfter).toEqual(expect.arrayContaining(behindBefore));
      }
    }
  });

  it('keeps a heavy task due today first on the worst day', () => {
    const approaches = plan([LIGHT, ROUTINE, DUE_TODAY], { availableHours: 0.5, energy: 'low' });

    for (const id of APPROACHES) {
      expect(order(approaches, id)[0]).toBe(DUE_TODAY.text);
    }
  });

  // interpret() puts "tomorrow" at 23:59, which scores as 2 days away
  it('protects a parsed "tomorrow" deadline from the goals in Consistency Focus', () => {
    const { items } = interpret(
      'Finish math assignment tomorrow, keep up daily DSA practice, build portfolio site',
      NOW,
    );
    const approaches = plan(items, { availableHours: 1, energy: 'low' });

    expect(order(plan(items), 'consistency')[0]).toBe('Finish math assignment');
    expect(order(approaches, 'consistency')[0]).toBe('Finish math assignment');
  });

  it('still lets energy move a deadline that is weeks away', () => {
    const later = dueIn(20, 'Write the seminar report', { category: 'upcoming' });
    const context = { availableHours: 1, energy: 'low' as const };

    expect(ahead(order(plan([later, LIGHT]), 'balanced'), later, LIGHT)).toBe(true);
    expect(ahead(order(plan([later, LIGHT], context), 'balanced'), LIGHT, later)).toBe(true);
  });

  // heavy item at 1 hour and low energy, Balanced: a full penalty is 3.5
  it.each([
    { bonus: 0, penalty: 3.5 },
    { bonus: 1, penalty: 7 / 3 },
    { bonus: 2, penalty: 7 / 6 },
    { bonus: 3, penalty: 0 },
    { bonus: 4, penalty: 0 },
  ])('takes $penalty off a heavy item with a +$bonus proximity bonus', ({ bonus, penalty }) => {
    const context = { availableHours: 1, energy: 'low' as const };

    expect(contextPenalty(HEAVY, 'balanced', bonus, context)).toBeCloseTo(penalty);
  });

  it('takes nothing off urgent work or routines', () => {
    const context = { availableHours: 1, energy: 'low' as const };

    expect(contextPenalty(URGENT, 'consistency', 0, context)).toBe(0);
    expect(contextPenalty(ROUTINE, 'consistency', 0, context)).toBe(0);
  });

  it('reacts least under Deadline Focus and most under Consistency Focus', () => {
    const context = { availableHours: 1, energy: 'low' as const };

    expect(contextPenalty(HEAVY, 'deadline', 0, context)).toBe(1.75);
    expect(contextPenalty(HEAVY, 'balanced', 0, context)).toBe(3.5);
    expect(contextPenalty(HEAVY, 'consistency', 0, context)).toBe(5.25);
  });

  it('sinks light work when there is room to spare, and only then', () => {
    const roomy = { availableHours: 8, energy: 'high' as const };

    expect(contextPenalty(LIGHT, 'balanced', 0, roomy)).toBe(2.5);
    expect(contextPenalty(HEAVY, 'balanced', 0, roomy)).toBe(0);
    expect(contextPenalty(LIGHT, 'balanced', 0, { availableHours: 1, energy: 'low' })).toBe(0);
  });
});

describe('the three approaches stay distinct', () => {
  const ITEMS = [
    dueIn(0.25, 'Finish the lab report', { priority: 'low' }),
    dueIn(10, 'Plan the college fest', { category: 'upcoming', priority: 'low' }),
    task('Write the club newsletter', { priority: 'high' }),
    task('Call the bank'),
    task('Daily DSA practice', { category: 'goal', priority: 'medium' }),
  ];

  it.each(COMBOS)('at $availableHours hours, $energy energy', context => {
    const approaches = plan(ITEMS, context);

    expect(approaches.map(a => a.id)).toEqual(APPROACHES);
    for (const approach of approaches) {
      expect(approach.items).toHaveLength(ITEMS.length);
    }

    const orders = APPROACHES.map(id => order(approaches, id).join('|'));
    expect(new Set(orders).size).toBe(3);

    // Deadline Focus still opens on the deadline, Consistency keeps the habit above other work
    expect(order(approaches, 'deadline')[0]).toBe('Finish the lab report');
    expect(order(approaches, 'consistency').slice(0, 2)).toContain('Daily DSA practice');
  });
});

describe('contextNote', () => {
  it.each([
    { context: { availableHours: 2 }, flagged: true },
    { context: { availableHours: 1, energy: 'low' }, flagged: true },
    { context: { energy: 'low' }, flagged: true },
    { context: { availableHours: 3 }, flagged: false },
    { context: { availableHours: 1, energy: 'high' }, flagged: false },
    { context: { availableHours: 8, energy: 'high' }, flagged: false },
    { context: {}, flagged: false },
  ] as Array<{ context: PlanningContext; flagged: boolean }>)('flags heavy work for $context: $flagged', ({ context, flagged }) => {
    expect(contextNote(HEAVY, context) !== '').toBe(flagged);
  });

  it('only flags heavy items', () => {
    const context = { availableHours: 1, energy: 'low' as const };

    expect(contextNote(STANDARD, context)).toBe('');
    expect(contextNote(LIGHT, context)).toBe('');
    expect(contextNote(ROUTINE, context)).toBe('');
  });

  it('shows up in the framing, including on a deadline that stays first', () => {
    const due = dueIn(0.25, 'Finish the lab report');
    const [deadline] = plan([due, LIGHT], { availableHours: 1, energy: 'low' });

    expect(deadline.items[0].item.text).toBe(due.text);
    expect(deadline.items[0].framing).toMatch(/Clear this first\. Heavy for today/);
    expect(deadline.items[1].framing).not.toMatch(/Heavy for today/);
  });
});
