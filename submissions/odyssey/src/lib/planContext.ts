/**
 * Odyssey Planner Context
 *
 * Turns what the user said on the Capture screen (hours, energy, habits) into a
 * score penalty for the planner. Still deterministic, no external API.
 *
 * Context only ever pushes items down, and it never pushes down something that
 * is urgent or due in the next few days. So a stretched day can change what comes
 * next, but it can't bury a real deadline under lighter work.
 */

import type { InterpretedItem } from './interpreter';
import type { ApproachId, CaptureContext, EnergyLevel } from './odysseyTypes';

export type PlanningContext = Partial<
  Pick<CaptureContext, 'availableHours' | 'energy' | 'consistencyGoals'>
>;

export type ItemEffort = 'light' | 'standard' | 'heavy' | 'routine';

// ─── Tuning ───────────────────────────────────────────────────────────────────

// The Capture screen defaults. 4 hours at medium energy leaves the plan as it is.
const NEUTRAL_HOURS = 4;
const ENERGY_ROOM: Record<EnergyLevel, number> = { low: -2, medium: 0, high: 1 };

// How hard each approach reacts. Deadline Focus moves least, Consistency most,
// so the approaches keep their own character on top of their category weights.
const APPROACH_REACTION: Record<ApproachId, number> = { deadline: 0.5, balanced: 1, consistency: 1.5 };

// Share of the penalty an item takes on a stretched day. On a day with room to
// spare it flips: light work sinks so demanding work can come first.
const EFFORT_DEMAND: Record<Exclude<ItemEffort, 'routine'>, number> = { light: 0, standard: 0.5, heavy: 1 };

// Proximity bonus from scoreItem() at which an item is fully protected. 3 means
// due within 3 days, and "tomorrow" needs that: it is parsed as 23:59 tomorrow,
// which counts as 2 days away.
const PROTECTED_PROXIMITY = 3;

// At or below this the heavy items get flagged, 2 hours at medium energy
const STRETCHED_ROOM = -1;

/** Added to the framing of heavy items on a stretched day */
export const HEAVY_NOTE = ' Heavy for today, start with one small piece.';

const LIGHT_WORK = /^(quick\s+)?(e-?mail|mail|reply|respond|call|phone|text|message|ping|remind|book|schedule|confirm|pay|renew|buy|order|print|send|sign|upload|check|clean|tidy|water|cancel|return|pick\s+up|drop\s+off)\b/i;
const HEAVY_WORK = /\b(exams?|midterms?|finals|thesis|dissertation|essays?|reports?|papers?|projects?|assignments?|presentations?|slides|proposals?|portfolio|research|study|studying|revise|revision|prepare|implement|build|develop|refactor|debug|migrate|design|write|draft|analy[sz]e)\b/i;

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Rough effort guess from the item alone, there are no time estimates at this
 * stage. The first word decides light work, so "Email the report" is an email.
 */
export function itemEffort(item: InterpretedItem, consistencyGoals: string[] = []): ItemEffort {
  const text = item.text.trim();
  const isNamedGoal = consistencyGoals.some(g => g.trim().toLowerCase() === text.toLowerCase());
  if (item.category === 'goal' || isNamedGoal) return 'routine';
  if (LIGHT_WORK.test(text)) return 'light';
  if (HEAVY_WORK.test(text)) return 'heavy';
  return 'standard';
}

/**
 * How much room the user has today. Negative is stretched, positive is room to
 * spare, 0 is neutral. Half an hour moves it by 0.25, capped at 7 hours because
 * a long free day doesn't make up for having no energy.
 */
export function capacity({ availableHours = NEUTRAL_HOURS, energy = 'medium' }: PlanningContext): number {
  return Math.min(1.5, (availableHours - NEUTRAL_HOURS) / 2) + ENERGY_ROOM[energy];
}

// ─── Used by the planner ──────────────────────────────────────────────────────

/** Points to take off an item's score. Always 0 with no context or a neutral one. */
export function contextPenalty(
  item: InterpretedItem,
  approach: ApproachId,
  proximityBonus: number,
  context: PlanningContext = {},
): number {
  const effort = itemEffort(item, context.consistencyGoals);
  if (effort === 'routine') return 0;

  const room = capacity(context);
  const demand = EFFORT_DEMAND[effort];
  const strain = room < 0 ? -room * demand : room * (1 - demand);

  // Urgent or due soon takes no penalty, and it fades in as the deadline moves out
  const shield = item.priority === 'urgent' ? 1 : Math.min(1, proximityBonus / PROTECTED_PROXIMITY);
  return strain * APPROACH_REACTION[approach] * (1 - shield);
}

/** Extra framing for heavy items on a stretched day, empty otherwise. */
export function contextNote(item: InterpretedItem, context: PlanningContext = {}): string {
  const isHeavy = itemEffort(item, context.consistencyGoals) === 'heavy';
  return isHeavy && capacity(context) <= STRETCHED_ROOM ? HEAVY_NOTE : '';
}
