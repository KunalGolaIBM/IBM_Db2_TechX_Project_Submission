/**
 * Odyssey Planner
 *
 * Takes a set of InterpretedItems and produces three PlanApproach objects.
 * All approaches work on the SAME items — they differ only in weighting and
 * the emphasis/framing they apply to each item.
 *
 * No external API. Fully deterministic.
 */

import type { InterpretedItem, ItemCategory } from './interpreter';
import type { TaskPriority } from '../types/database';
import type { CreateMissionInput } from '../services/missionService';
import { contextNote, contextPenalty, type PlanningContext } from './planContext';

// ─── Types ────────────────────────────────────────────────────────────────────

export type ApproachId = 'deadline' | 'balanced' | 'consistency';

export interface ApproachItem {
  item: InterpretedItem;
  /** Human-readable framing for this item under the chosen approach */
  framing: string;
  /** 0–10 emphasis level — used to show visual weight */
  emphasis: number;
}

export interface PlanApproach {
  id: ApproachId;
  emoji: string;
  name: string;
  tagline: string;
  description: string;
  /** Items sorted and framed for this approach */
  items: ApproachItem[];
}

// ─── Weight tables ────────────────────────────────────────────────────────────

// Category weights per strategy (higher = more prominent in the ordering)
const CATEGORY_WEIGHTS: Record<ApproachId, Record<ItemCategory, number>> = {
  deadline:    { deadline: 10, upcoming: 7, task: 4, goal: 1 },
  balanced:    { deadline:  8, upcoming: 6, task: 5, goal: 4 },
  consistency: { deadline:  6, upcoming: 5, task: 4, goal: 9 },
};

// Priority multiplier — applies on top of category weight
const PRIORITY_BONUS: Record<TaskPriority, number> = {
  urgent: 3,
  high:   2,
  medium: 1,
  low:    0,
};

// ─── Framing sentences ────────────────────────────────────────────────────────

function framingFor(
  item: InterpretedItem,
  approach: ApproachId,
  emphasis: number,
): string {
  const { category, deadlineLabel } = item;
  const dl = deadlineLabel ? ` — ${deadlineLabel}` : '';

  if (approach === 'deadline') {
    if (category === 'deadline')    return `Deadline${dl}. Clear this first.`;
    if (category === 'upcoming')    return `Upcoming${dl}. Start preparing now.`;
    if (category === 'task')        return 'Address after deadline-critical work.';
    /* goal */                       return 'Keep in view — resume after urgent work clears.';
  }

  if (approach === 'balanced') {
    if (category === 'deadline')    return `Deadline${dl}. Keep this on track.`;
    if (category === 'upcoming')    return `Scheduled${dl}. Steady progress.`;
    if (category === 'task')        return 'Part of your balanced workload.';
    /* goal */                       return 'Weave this into your regular rhythm.';
  }

  // consistency
  if (category === 'goal')          return emphasis >= 7 ? 'Core habit — protect this time.' : 'Maintain consistently.';
  if (category === 'deadline')      return `Deadline${dl}. Handle this, then return to habits.`;
  if (category === 'upcoming')      return `Prepare${dl}. Don't let it crowd your routines.`;
  /* task */                         return 'Complete when it fits your rhythm.';
}

// ─── Score function ───────────────────────────────────────────────────────────

export function scoreItem(
  item: InterpretedItem,
  approach: ApproachId,
  referenceDate: Date = new Date(),
  context?: PlanningContext,
): number {
  const catWeight      = CATEGORY_WEIGHTS[approach][item.category];
  const priorityBonus  = PRIORITY_BONUS[item.priority];
  // Deadline proximity bonus: closer deadline = higher score
  let proximityBonus = 0;
  if (item.deadlineDate) {
    const daysAway = Math.max(
      0,
      Math.ceil((item.deadlineDate.getTime() - referenceDate.getTime()) / (1000 * 60 * 60 * 24))
    );
    // 0 days → +4, 7 days → +2, 14+ days → 0
    proximityBonus = Math.max(0, 4 - Math.floor(daysAway / 2));
  }
  return catWeight + priorityBonus + proximityBonus - contextPenalty(item, approach, proximityBonus, context);
}

// Normalise scores to 0-10 emphasis range within an approach
function normalise(scores: number[]): number[] {
  const max = Math.max(...scores, 1);
  const min = Math.min(...scores, 0);
  const range = max - min || 1;
  return scores.map(s => Math.round(((s - min) / range) * 10));
}

// ─── Mission derivation from approach ────────────────────────────────────────

import { deriveMissionFromTask } from './missionDerivation';

/**
 * Derives CreateMissionInput from the highest-weighted item in a PlanApproach.
 * Purely deterministic — no AI.
 */
export function missionFromApproach(approach: PlanApproach): CreateMissionInput {
  // Top item is already sorted by approach weight
  const top = approach.items[0];
  if (!top) {
    return { title: 'Mission', objective: null, next_action: null, planned_minutes: 25 };
  }

  const { item, framing } = top;
  const derived = deriveMissionFromTask({
    title: item.text,
    description: framing,
    deadline: item.isoDeadline ?? null,
    priority: item.priority,
  });

  return {
    title:           derived.title,
    task_id:         null,
    objective:       derived.objective,
    next_action:     derived.next_action,
    planned_minutes: derived.planned_minutes,
  };
}

export function buildApproaches(
  items: InterpretedItem[],
  referenceDate: Date = new Date(),
  context?: PlanningContext,
): PlanApproach[] {
  if (items.length === 0) return [];

  const approaches: Array<{ id: ApproachId; emoji: string; name: string; tagline: string; description: string }> = [
    {
      id:          'deadline',
      emoji:       '⚡',
      name:        'Deadline Focus',
      tagline:     "Clear what can't wait first.",
      description: 'Prioritise the most urgent and time-sensitive commitments. Everything else waits until deadlines are under control.',
    },
    {
      id:          'balanced',
      emoji:       '⚖️',
      name:        'Balanced',
      tagline:     'Steady progress across everything.',
      description: 'Spread attention across deadlines, upcoming work, and ongoing goals. No single area dominates — you stay on track on all fronts.',
    },
    {
      id:          'consistency',
      emoji:       '🌱',
      name:        'Consistency Focus',
      tagline:     'Keep the habits going.',
      description: 'Give more weight to ongoing goals and habits while still respecting what\'s due. Momentum on long-term work is treated as essential, not optional.',
    },
  ];

  return approaches.map(({ id, emoji, name, tagline, description }) => {
    const rawScores = items.map(item => scoreItem(item, id, referenceDate, context));
    const normScores = normalise(rawScores);

    // Pair items with their normalised scores, sort descending
    const scored = items.map((item, i) => ({
      item,
      rawScore: rawScores[i],
      emphasis: normScores[i],
    }));
    scored.sort((a, b) => b.rawScore - a.rawScore);

    // Re-normalise emphasis after sorting (same values, stable after sort)
    const approachItems: ApproachItem[] = scored.map(({ item, emphasis }) => ({
      item,
      emphasis,
      framing: framingFor(item, id, emphasis) + contextNote(item, context),
    }));

    return { id, emoji, name, tagline, description, items: approachItems };
  });
}
