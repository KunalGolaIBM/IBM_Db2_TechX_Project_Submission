/**
 * Odyssey AI Service
 *
 * Client-side wrapper around the suggest-mission Supabase Edge Function.
 * All three operations (interpret, plan, suggest_mission) route through one
 * deployed function. The Gemini API key never touches the browser.
 *
 * Every function returns null on any failure — callers fall back to the
 * deterministic interpreter/planner automatically.
 */

import { supabase } from '../lib/supabase';
import type {
  CaptureContext,
  AIInterpretation,
  AIItem,
  AIPlans,
  AIPlan,
  AIMission,
  ApproachId,
} from '../lib/odysseyTypes';
import { interpret } from '../lib/interpreter';          // deterministic fallback
import { buildApproaches } from '../lib/planner';         // deterministic fallback
import { HEAVY_NOTE } from '../lib/planContext';
import { isValidMissionDuration } from '../lib/missionDuration';

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function invoke<T>(body: Record<string, unknown>): Promise<T | null> {
  try {
    const { data, error } = await supabase.functions.invoke('suggest-mission', { body });
    if (error) {
      const ctx = (error as { context?: unknown }).context;
      console.warn(
        '[Odyssey AI] Edge function error.',
        '\n  operation:', body.operation,
        '\n  error.message:', error.message,
        '\n  error.context:', JSON.stringify(ctx ?? '(none)'),
      );
      return null;
    }
    if (!data) {
      console.warn('[Odyssey AI] Edge function returned empty data. operation:', body.operation);
      return null;
    }
    // Check if the function returned an error body (e.g. 502 with {error, model})
    if (typeof data === 'object' && data !== null && 'error' in data) {
      console.warn(
        '[Odyssey AI] Edge function returned error body:',
        JSON.stringify(data),
        '\n  operation:', body.operation,
      );
      return null;
    }
    console.info('[Odyssey AI] Edge function success. operation:', body.operation);
    return data as T;
  } catch (err) {
    console.warn('[Odyssey AI] Edge function threw unexpectedly:', err);
    return null;
  }
}

/** Format the current date for sending to Gemini */
function dateMeta(): { iso: string; label: string } {
  const now = new Date();
  const iso  = now.toISOString();
  const label = now.toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });
  return { iso, label };
}

// ─── 1. interpretCapture ──────────────────────────────────────────────────────

/**
 * Send the capture context to Gemini for interpretation.
 * Falls back to the local deterministic interpreter if AI is unavailable.
 *
 * Always returns a non-null AIInterpretation.
 */
export async function interpretCapture(ctx: CaptureContext): Promise<AIInterpretation> {
  const { iso, label } = dateMeta();

  const data = await invoke<{ items: AIItem[] }>({
    operation:          'interpret',
    raw_input:          ctx.rawInput,
    available_hours:    ctx.availableHours,
    energy:             ctx.energy,
    consistency_goals:  ctx.consistencyGoals,
    horizon:            ctx.horizon,
    current_date_iso:   iso,
    current_date_label: label,
  });

  if (data?.items && Array.isArray(data.items) && data.items.length > 0) {
    // Merge any structured consistency goals not already present
    const existingTexts = new Set(data.items.map(i => i.text.toLowerCase()));
    const extraGoals: AIItem[] = ctx.consistencyGoals
      .filter(g => g.trim() && !existingTexts.has(g.trim().toLowerCase()))
      .map(g => ({
        text:          g.trim(),
        category:      'goal' as const,
        deadlineLabel: null,
        isoDeadline:   null,
        priority:      'low' as const,
        isConsistency: true,
        ambiguity:     null,
      }));

    return { items: [...data.items, ...extraGoals], aiGenerated: true };
  }

  // ── Deterministic fallback ────────────────────────────────────────────────
  console.warn('[Odyssey AI] interpretCapture: AI unavailable, using deterministic fallback');
  const fallback = interpret(ctx.rawInput);

  const items: AIItem[] = fallback.items.map(item => ({
    text:          item.text,
    category:      item.category,
    deadlineLabel: item.deadlineLabel ?? null,
    isoDeadline:   item.isoDeadline   ?? null,
    priority:      item.priority,
    isConsistency: item.category === 'goal',
    ambiguity:     null,
  }));

  // Add structured consistency goals not caught by the fallback parser
  const existingTexts = new Set(items.map(i => i.text.toLowerCase()));
  for (const g of ctx.consistencyGoals) {
    if (g.trim() && !existingTexts.has(g.trim().toLowerCase())) {
      items.push({
        text:          g.trim(),
        category:      'goal',
        deadlineLabel: null,
        isoDeadline:   null,
        priority:      'low',
        isConsistency: true,
        ambiguity:     null,
      });
    }
  }

  return { items, aiGenerated: false };
}

// ─── 2. generatePlans ─────────────────────────────────────────────────────────

/**
 * Send interpreted items + context to Gemini to generate three plans.
 * Falls back to the deterministic planner if AI is unavailable.
 *
 * Always returns a non-null AIPlans.
 */
export async function generatePlans(
  ctx: CaptureContext,
  interpretation: AIInterpretation,
): Promise<AIPlans> {
  const { label } = dateMeta();

  const data = await invoke<{ plans: AIPlan[] }>({
    operation:          'plan',
    raw_input:          ctx.rawInput,
    available_hours:    ctx.availableHours,
    energy:             ctx.energy,
    consistency_goals:  ctx.consistencyGoals,
    horizon:            ctx.horizon,
    current_date_label: label,
    items:              interpretation.items.map(i => ({
      text:          i.text,
      category:      i.category,
      deadlineLabel: i.deadlineLabel ?? null,
      isoDeadline:   i.isoDeadline   ?? null,
      priority:      i.priority,
      isConsistency: i.isConsistency,
    })),
  });

  if (data?.plans && Array.isArray(data.plans) && data.plans.length === 3) {
    return { plans: data.plans as [AIPlan, AIPlan, AIPlan], aiGenerated: true };
  }

  // ── Deterministic fallback ────────────────────────────────────────────────
  console.warn('[Odyssey AI] generatePlans: AI unavailable, using deterministic fallback');
  return deterministicPlans(ctx, interpretation);
}

function deterministicPlans(ctx: CaptureContext, interpretation: AIInterpretation): AIPlans {
  // Map AIItems back to InterpretedItems for the existing planner
  const interpretedItems = interpretation.items.map(ai => ({
    text:          ai.text,
    category:      ai.category,
    deadlineLabel: ai.deadlineLabel ?? undefined,
    deadlineDate:  ai.isoDeadline ? new Date(ai.isoDeadline) : undefined,
    priority:      ai.priority,
    isoDeadline:   ai.isoDeadline ?? undefined,
  }));

  const approaches = buildApproaches(interpretedItems, new Date(), ctx);

  const plans: AIPlan[] = approaches.map(approach => ({
    id:              approach.id as ApproachId,
    emoji:           approach.emoji,
    name:            approach.name,
    tagline:         approach.tagline,
    whyThisApproach: approach.description,
    orderedItems:    approach.items.map(ai => ({
      text:          ai.item.text,
      deadlineLabel: ai.item.deadlineLabel ?? null,
      priority:      ai.item.priority,
      rationale:     ai.framing,
    })),
    timeEstimate:    'Based on your task list',
    tradeoff:        approach.id === 'deadline'
      ? 'Consistency goals take a back seat until deadlines are cleared.'
      : approach.id === 'consistency'
      ? 'Deadline work may take longer — habit time is protected.'
      : 'No single concern dominates; progress is spread across all areas.',
  }));

  // Ensure exactly three plans in the correct order
  const ordered = (['deadline', 'balanced', 'consistency'] as ApproachId[]).map(
    id => plans.find(p => p.id === id)!
  );

  return { plans: ordered as [AIPlan, AIPlan, AIPlan], aiGenerated: false };
}

// ─── 3. suggestMissionFromPlan ────────────────────────────────────────────────

/**
 * Given the user's chosen plan and full context, ask Gemini to generate
 * the first concrete mission.
 * Falls back to missionFromApproach() if AI is unavailable.
 *
 * Always returns a non-null AIMission.
 */
export async function suggestMissionFromPlan(
  ctx: CaptureContext,
  chosenPlan: AIPlan,
): Promise<AIMission> {
  const { label } = dateMeta();
  const firstItem = chosenPlan.orderedItems[0];
  if (!firstItem) {
    return deterministicMission(ctx, chosenPlan);
  }

  const data = await invoke<{
    title: string; objective: string; next_action: string;
    planned_minutes: number; reasoning: string;
  }>({
    operation:           'suggest_mission',
    raw_input:           ctx.rawInput,
    available_hours:     ctx.availableHours,
    energy:              ctx.energy,
    current_date_label:  label,
    selected_plan_id:    chosenPlan.id,
    selected_plan_name:  chosenPlan.name,
    selected_plan_why:   chosenPlan.whyThisApproach,
    first_item_text:     firstItem.text,
    first_item_deadline: firstItem.deadlineLabel ?? null,
    all_items_summary:   chosenPlan.orderedItems.map(i => i.text).join(', '),
  });

  if (
    data?.title && data?.objective && data?.next_action &&
    isValidMissionDuration(data?.planned_minutes)
  ) {
    return {
      title:           data.title,
      objective:       data.objective,
      next_action:     data.next_action,
      planned_minutes: data.planned_minutes,
      reasoning:       data.reasoning ?? '',
      aiGenerated:     true,
    };
  }

  console.warn('[Odyssey AI] suggestMissionFromPlan: AI unavailable, using deterministic fallback');
  return deterministicMission(ctx, chosenPlan);
}

import { deriveMissionFromTask } from '../lib/missionDerivation';
import type { Task } from '../types/database';

export async function suggestMissionForTask(
  task: Task,
  context?: Partial<CaptureContext>,
): Promise<AIMission> {
  const { label } = dateMeta();
  const deadlineStr = task.deadline ? new Date(task.deadline).toLocaleDateString('en-GB') : null;

  const data = await invoke<{
    title: string; objective: string; next_action: string;
    planned_minutes: number; reasoning: string;
  }>({
    operation:           'suggest_mission',
    raw_input:           task.description || task.title,
    available_hours:     context?.availableHours ?? 2,
    energy:              context?.energy ?? 'medium',
    current_date_label:  label,
    selected_plan_id:    'focus',
    selected_plan_name:  'Focused Execution',
    selected_plan_why:   'Direct task execution',
    first_item_text:     task.title,
    first_item_deadline: deadlineStr,
    all_items_summary:   task.title + (task.description ? ` (${task.description})` : ''),
  });

  if (
    data?.title && data?.objective && data?.next_action &&
    isValidMissionDuration(data?.planned_minutes)
  ) {
    return {
      title:           data.title,
      objective:       data.objective,
      next_action:     data.next_action,
      planned_minutes: data.planned_minutes,
      reasoning:       data.reasoning ?? '',
      aiGenerated:     true,
    };
  }

  // Fallback to intelligent deterministic generator
  const derived = deriveMissionFromTask(task);
  return {
    title:           derived.title,
    objective:       derived.objective,
    next_action:     derived.next_action,
    planned_minutes: derived.planned_minutes,
    reasoning:       `Focused action derived from "${task.title}".`,
    aiGenerated:     false,
  };
}

function deterministicMission(ctx: CaptureContext, plan: AIPlan): AIMission {
  const first = plan.orderedItems[0];
  if (!first) {
    return {
      title:           ctx.rawInput.slice(0, 50).trim() || 'Next Mission',
      objective:       'Clear the most critical open blocker for today.',
      next_action:     'Open your workspace and begin the primary item.',
      planned_minutes: 25,
      reasoning:       'Starting with the top-priority item.',
      aiGenerated:     false,
    };
  }

  const derived = deriveMissionFromTask({
    title: first.text,
    // The note is advice for the plan card, not part of the mission objective
    description: first.rationale.replace(HEAVY_NOTE, ''),
    deadline: first.deadlineLabel,
    priority: first.priority,
  });

  return {
    title:           derived.title,
    objective:       derived.objective,
    next_action:     derived.next_action,
    planned_minutes: derived.planned_minutes,
    reasoning:       `Targeted action for ${plan.name}: "${first.text}".`,
    aiGenerated:     false,
  };
}
