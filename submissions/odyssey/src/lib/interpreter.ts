/** 
 * Odyssey Input Interpreter
 *
 * Deterministic, client-side natural-language analysis.
 * No external API required. Parses free-text capture input into structured
 * InterpretedItems that can be shown to the user and saved as Tasks
 */

import type { TaskPriority } from '../types/database';

// ─── Output types ─────────────────────────────────────────────────────────────

export type ItemCategory =
  | 'deadline'   // has a near deadline (≤7 days)
  | 'upcoming'   // has a deadline further out (>7 days)
  | 'goal'       // ongoing / habitual / open-ended
  | 'task';      // generic discrete task

export interface InterpretedItem {
  text: string;
  category: ItemCategory;
  deadlineLabel?: string;
  deadlineDate?: Date;
  priority: TaskPriority;
  isoDeadline?: string;
}

export interface InterpretationResult {
  items: InterpretedItem[];
  rawInput: string;
}

// ─── Deadline detection ───────────────────────────────────────────────────────

/** Day-name patterns and their offsets from today (0 = same weekday ahead) */
const DAY_NAMES: Record<string, number> = {
  sunday: 0, sun: 0,
  monday: 1, mon: 1,
  tuesday: 2, tue: 2,
  wednesday: 3, wed: 3,
  thursday: 4, thu: 4,
  friday: 5, fri: 5,
  saturday: 6, sat: 6,
};

/**
 * Return the next occurrence of a weekday.
 * A bare weekday may include today; explicit "next <weekday>" must be
 * strictly after today, so "next Monday" entered on Monday means +7 days.
 */
function nextWeekdayDate(targetDay: number, referenceDate: Date, includeToday = false): Date {
  const today = new Date(referenceDate);
  today.setHours(23, 59, 0, 0);
  const current = today.getDay();
  let diff = targetDay - current;
  if (diff < 0 || (diff === 0 && !includeToday)) diff += 7;
  const d = new Date(today);
  d.setDate(d.getDate() + diff);
  return d;
}

interface DeadlineParse {
  label: string;
  date: Date;
}

function parseDeadline(text: string, referenceDate: Date): DeadlineParse | null {
  const lower = text.toLowerCase();
  const today = new Date(referenceDate);
  today.setHours(23, 59, 0, 0);

  if (/\btoday\b/.test(lower)) {
    return { label: 'today', date: today };
  }
  if (/\btomorrow\b/.test(lower)) {
    const d = new Date(today);
    d.setDate(d.getDate() + 1);
    return { label: 'tomorrow', date: d };
  }
  if (/\bthis\s+week\b|\bend\s+of\s+(the\s+)?week\b/.test(lower)) {
    // The app treats Friday as the end of the current week. On Saturday or
    // Sunday, that Friday has already passed; don't roll into next week.
    const day = today.getDay();
    const offset = day === 0 ? -2 : day === 6 ? -1 : 5 - day;
    const d = new Date(today);
    d.setDate(d.getDate() + offset);
    return { label: 'this week', date: d };
  }
  if (/\bnext\s+week\b/.test(lower)) {
    const d = new Date(today);
    d.setDate(d.getDate() + 7);
    return { label: 'next week', date: d };
  }
  const nextDayMatch = lower.match(/\bnext\s+(sunday|sun|monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat)\b/);
  if (nextDayMatch) {
    const dayNum = DAY_NAMES[nextDayMatch[1]];
    const d = nextWeekdayDate(dayNum, today);
    const label = 'next ' + nextDayMatch[1].charAt(0).toUpperCase() + nextDayMatch[1].slice(1, 3);
    return { label, date: d };
  }
  const dayMatch = lower.match(/\b(sunday|sun|monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat)\b/);
  if (dayMatch) {
    const dayNum = DAY_NAMES[dayMatch[1]];
    const d = nextWeekdayDate(dayNum, today, true);
    const label = dayMatch[1].charAt(0).toUpperCase() + dayMatch[1].slice(1, 3);
    return { label, date: d };
  }
  const inDaysMatch = lower.match(/\bin\s+(\d+)\s+(day|days)\b/);
  if (inDaysMatch) {
    const n = parseInt(inDaysMatch[1], 10);
    const d = new Date(today);
    d.setDate(d.getDate() + n);
    return { label: `in ${n} day${n === 1 ? '' : 's'}`, date: d };
  }
  const inWeeksMatch = lower.match(/\bin\s+(\d+)\s+(week|weeks)\b/);
  if (inWeeksMatch) {
    const n = parseInt(inWeeksMatch[1], 10);
    const d = new Date(today);
    d.setDate(d.getDate() + n * 7);
    return { label: `in ${n} week${n === 1 ? '' : 's'}`, date: d };
  }
  return null;
}

function parsePriority(text: string): TaskPriority {
  const lower = text.toLowerCase();
  if (/\b(urgent|asap|critical|emergency|immediately|right away|must\s+do|need\s+to\s+do\s+now)\b/.test(lower)) return 'urgent';
  if (/\b(important|high\s+priority|really\s+need|crucial|significant|key|major)\b/.test(lower)) return 'high';
  if (/\b(keep|continue|ongoing|habit|practice|learning|study|explore|read|want\s+to)\b/.test(lower)) return 'low';
  return 'medium';
}

function isOngoingGoal(text: string): boolean {
  const lower = text.toLowerCase();
  return /\b(keep|continue|ongoing|habit|practice|learning|study|explore|read|want\s+to|trying\s+to|working\s+on|improve|get\s+better|build|develop|maintain)\b/.test(lower);
}

function cleanTitle(text: string): string {
  return text
    .replace(/\b(due|by|on|before|for|until|at|around)\s+(next\s+)?(sunday|sun|monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat)\b/gi, '')
    .replace(/\bnext\s+(sunday|sun|monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat)\b/gi, '')
    .replace(/\b(sunday|sun|monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat)\b/gi, '')
    .replace(/\btoday\b/gi, '')
    .replace(/\btomorrow\b/gi, '')
    .replace(/\bthis\s+week\b/gi, '')
    .replace(/\bnext\s+week\b/gi, '')
    .replace(/\bin\s+\d+\s+(day|days|week|weeks)\b/gi, '')
    .replace(/\b(urgent|asap|important|high\s+priority)\b/gi, '')
    .replace(/\s{2,}/g, ' ')
    .replace(/^[\s,;.]+|[\s,;.]+$/g, '')
    .trim();
}

// ─── Sentence / clause splitting ─────────────────────────────────────────────

/**
 * Split free-form input into individual clauses.
 * Handles: comma lists, "and" between multi-word phrases, semicolons, sentence boundaries.
 */
export function splitClauses(input: string): string[] {
  // Normalise line breaks
  const normalised = input.replace(/\r?\n/g, ', ');

  // Hard boundaries: comma, semicolon, sentence end (period + space + capital)
  const segments = normalised.split(/,\s*|\s*;\s*|\.\s+(?=[A-Z])/);

  // "and" only separates tasks when both sides are phrases of 2+ words.
  // This keeps titles like "Research and Development proposal" or "Q and A prep" intact.
  return segments
    .flatMap(splitOnAnd)
    .map(s => s.trim())
    .filter(s => s.length > 2);
}

const MIN_WORDS_PER_SIDE = 2;

function splitOnAnd(segment: string): string[] {
  const words = segment.trim().split(/\s+/);
  const parts: string[] = [];
  let current: string[] = [];

  words.forEach((word, i) => {
    const remaining = words.length - i - 1;
    if (
      word.toLowerCase() === 'and' &&
      current.length >= MIN_WORDS_PER_SIDE &&
      remaining >= MIN_WORDS_PER_SIDE
    ) {
      parts.push(current.join(' '));
      current = [];
    } else {
      current.push(word);
    }
  });
  if (current.length) parts.push(current.join(' '));
  return parts;
}

function assignCategory(text: string, deadline: DeadlineParse | null, referenceDate: Date): ItemCategory {
  if (!deadline) return isOngoingGoal(text) ? 'goal' : 'task';
  const daysAway = Math.ceil((deadline.date.getTime() - referenceDate.getTime()) / (1000 * 60 * 60 * 24));
  return daysAway <= 7 ? 'deadline' : 'upcoming';
}

export function interpret(rawInput: string, referenceDate = new Date()): InterpretationResult {
  const clauses = splitClauses(rawInput);
  const items: InterpretedItem[] = clauses.map((clause): InterpretedItem => {
    const deadline = parseDeadline(clause, referenceDate);
    const priority = parsePriority(clause);
    const category = assignCategory(clause, deadline, referenceDate);
    const cleanedTitle = cleanTitle(clause);
    return {
      text: cleanedTitle || clause.trim(),
      category,
      deadlineLabel: deadline?.label,
      deadlineDate: deadline?.date,
      priority,
      isoDeadline: deadline?.date?.toISOString(),
    };
  });
  const ORDER: Record<ItemCategory, number> = { deadline: 0, upcoming: 1, task: 2, goal: 3 };
  items.sort((a, b) => {
    const orderDiff = ORDER[a.category] - ORDER[b.category];
    if (orderDiff !== 0) return orderDiff;
    if (a.deadlineDate && b.deadlineDate) return a.deadlineDate.getTime() - b.deadlineDate.getTime();
    return 0;
  });
  return { items, rawInput };
}
