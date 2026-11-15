/**
 * Odyssey shared types for the CAPTURE → UNDERSTAND → PLAN → EXECUTE flow.
 *
 * These types cross the boundary between Home.tsx, Mission.tsx, aiService.ts,
 * and the Edge Function. Keeping them here avoids circular imports.
 */

// ─── Capture context (user-provided structured fields) ────────────────────────

export type EnergyLevel  = 'low' | 'medium' | 'high';
export type PlanHorizon  = 'today' | 'this_week' | 'custom';

/**
 * All structured context collected from the Capture screen.
 * Passed to Gemini for interpretation and planning.
 */
export interface CaptureContext {
  /** The raw free-text brain dump */
  rawInput: string;
  /** Hours the user realistically has available today (0.5–12) */
  availableHours: number;
  /** User's current energy level */
  energy: EnergyLevel;
  /** Ongoing habits/goals the user wants to protect */
  consistencyGoals: string[];
  /** Planning horizon */
  horizon: PlanHorizon;
  /** ISO timestamp — passed to Gemini so relative dates are resolved correctly */
  capturedAt: string;
}

// ─── AI interpretation result ─────────────────────────────────────────────────

export type AIItemCategory = 'deadline' | 'upcoming' | 'goal' | 'task';
export type AIPriority     = 'urgent' | 'high' | 'medium' | 'low';

/**
 * A single task/commitment/goal extracted by Gemini from the raw input.
 */
export interface AIItem {
  /** Cleaned task title */
  text: string;
  category: AIItemCategory;
  /** Human-readable deadline label, e.g. "Tonight · Aug 26" */
  deadlineLabel?: string | null;
  /** ISO date string if a deadline was identified */
  isoDeadline?: string | null;
  priority: AIPriority;
  /** True for ongoing habits/consistency goals */
  isConsistency: boolean;
  /** Any ambiguity Gemini flagged about this item */
  ambiguity?: string | null;
}

/**
 * Full structured interpretation returned by Gemini (or the deterministic fallback).
 */
export interface AIInterpretation {
  items: AIItem[];
  /** Whether this was produced by AI (true) or the deterministic fallback (false) */
  aiGenerated: boolean;
}

// ─── AI-generated plans ───────────────────────────────────────────────────────

export type ApproachId = 'deadline' | 'balanced' | 'consistency';

/**
 * A single item within an AI plan, ordered by the approach's logic.
 */
export interface AIPlanItem {
  text: string;
  deadlineLabel?: string | null;
  priority: AIPriority;
  /** Why this item is placed here in this particular approach */
  rationale: string;
}

/**
 * One of the three AI-generated planning approaches.
 */
export interface AIPlan {
  id: ApproachId;
  emoji: string;
  name: string;
  tagline: string;
  /** Why this approach makes sense given the current context */
  whyThisApproach: string;
  /** Ordered list of recommended work for this approach */
  orderedItems: AIPlanItem[];
  /** Estimated use of today's available time, e.g. "~3.5 of your 4 hours" */
  timeEstimate: string;
  /** The key tradeoff this approach makes */
  tradeoff: string;
}

/**
 * All three plans returned by Gemini.
 */
export interface AIPlans {
  plans: [AIPlan, AIPlan, AIPlan];
  aiGenerated: boolean;
}

// ─── AI-generated mission suggestion ─────────────────────────────────────────

export interface AIMission {
  title:           string;
  objective:       string;
  next_action:     string;
  planned_minutes: number;
  /** Concise reason why this is the right first mission given the approach + context */
  reasoning:       string;
  aiGenerated:     boolean;
}

// ─── Full context passed through router state ─────────────────────────────────

/**
 * What Home.tsx passes to Mission.tsx via React Router location.state.
 */
export interface OdysseyRouterState {
  captureContext:   CaptureContext;
  interpretation:   AIInterpretation;
  /** prefillTask is kept for backward-compat with the direct task→mission flow */
  prefillTask?:     { id: string; title: string; estimated_minutes?: number | null } | null;
}
