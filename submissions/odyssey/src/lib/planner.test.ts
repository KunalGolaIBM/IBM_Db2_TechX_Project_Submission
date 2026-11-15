import { afterEach, describe, expect, it, vi } from 'vitest';
import { buildApproaches, scoreItem } from './planner.ts';
import type { InterpretedItem } from './interpreter.ts';

const REFERENCE = new Date('2026-03-10T12:00:00.000Z');

function daysFromReference(days: number) {
  return new Date(REFERENCE.getTime() + days * 24 * 60 * 60 * 1000);
}

function deadlineItem(days: number, text = 'Finish lab report'): InterpretedItem {
  const deadlineDate = daysFromReference(days);
  return {
    text,
    category: 'deadline',
    deadlineLabel: `in ${days} days`,
    deadlineDate,
    priority: 'medium',
    isoDeadline: deadlineDate.toISOString(),
  };
}

const ITEMS: InterpretedItem[] = [
  { text: 'Keep up daily DSA', category: 'goal', priority: 'low' },
  { text: 'Clean the desk', category: 'task', priority: 'medium' },
  deadlineItem(9, 'Hand in project'),
  deadlineItem(1, 'Finish lab report'),
];

function textsFor(approaches: ReturnType<typeof buildApproaches>, id: string) {
  return approaches.find(a => a.id === id)?.items.map(a => a.item.text);
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('scoreItem with a reference date', () => {
  // deadline approach, medium priority: 10 category + 1 priority + proximity bonus
  it.each([
    { days: -2, bonus: 4 },
    { days: 0, bonus: 4 },
    { days: 1, bonus: 4 },
    { days: 2, bonus: 3 },
    { days: 4, bonus: 2 },
    { days: 7, bonus: 1 },
    { days: 8, bonus: 0 },
    { days: 30, bonus: 0 },
  ])('gives a +$bonus proximity bonus $days days out', ({ days, bonus }) => {
    expect(scoreItem(deadlineItem(days), 'deadline', REFERENCE)).toBe(11 + bonus);
  });

  it('rounds part of a day up, same as before', () => {
    const item = deadlineItem(1.25);
    expect(scoreItem(item, 'deadline', REFERENCE)).toBe(11 + 3);
    expect(scoreItem(item, 'deadline', daysFromReference(0.25))).toBe(11 + 4);
  });

  it('changes when the reference date moves, for the same item', () => {
    const item = deadlineItem(9);
    expect(scoreItem(item, 'balanced', REFERENCE)).toBe(9);
    expect(scoreItem(item, 'balanced', daysFromReference(8))).toBe(13);
  });

  it('adds no proximity bonus when the item has no deadline', () => {
    const item: InterpretedItem = { text: 'Keep up daily DSA', category: 'goal', priority: 'low' };
    expect(scoreItem(item, 'consistency', REFERENCE)).toBe(9);
    expect(scoreItem(item, 'consistency', daysFromReference(100))).toBe(9);
  });

  it('falls back to the current time when no reference date is passed', () => {
    vi.useFakeTimers();
    vi.setSystemTime(REFERENCE);
    const item = deadlineItem(2);
    expect(scoreItem(item, 'deadline')).toBe(scoreItem(item, 'deadline', REFERENCE));
    vi.setSystemTime(daysFromReference(8));
    expect(scoreItem(item, 'deadline')).toBe(scoreItem(item, 'deadline', daysFromReference(8)));
  });
});

describe('buildApproaches with a reference date', () => {
  it('orders items from the supplied date', () => {
    const approaches = buildApproaches(ITEMS, REFERENCE);

    expect(textsFor(approaches, 'deadline')).toEqual([
      'Finish lab report',
      'Hand in project',
      'Clean the desk',
      'Keep up daily DSA',
    ]);
    expect(textsFor(approaches, 'consistency')?.[0]).toBe('Finish lab report');
  });

  it('reorders items when the reference date moves closer to a deadline', () => {
    const justBefore = buildApproaches(ITEMS, daysFromReference(8.5));

    // the lab report is overdue and the project is now due in a day, both cap at +4
    expect(scoreItem(ITEMS[2], 'deadline', daysFromReference(8.5))).toBe(15);
    expect(scoreItem(ITEMS[3], 'deadline', daysFromReference(8.5))).toBe(15);
    expect(textsFor(justBefore, 'deadline')?.slice(0, 2)).toEqual(['Hand in project', 'Finish lab report']);
  });

  it('gives the same plan for the same date whatever the system clock says', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2020-01-01T00:00:00.000Z'));
    const first = buildApproaches(ITEMS, REFERENCE);
    vi.setSystemTime(new Date('2035-06-15T23:59:00.000Z'));
    const second = buildApproaches(ITEMS, REFERENCE);

    expect(second).toEqual(first);
  });

  it('never reads the system clock when a reference date is passed', () => {
    const now = vi.spyOn(Date, 'now');
    buildApproaches(ITEMS, REFERENCE);
    expect(now).not.toHaveBeenCalled();
  });

  it('matches the old behaviour when no reference date is passed', () => {
    vi.useFakeTimers();
    vi.setSystemTime(REFERENCE);

    expect(buildApproaches(ITEMS)).toEqual(buildApproaches(ITEMS, REFERENCE));
  });

  it('still returns all three approaches, and nothing for an empty list', () => {
    expect(buildApproaches(ITEMS, REFERENCE).map(a => a.id)).toEqual(['deadline', 'balanced', 'consistency']);
    expect(buildApproaches([], REFERENCE)).toEqual([]);
  });
});
