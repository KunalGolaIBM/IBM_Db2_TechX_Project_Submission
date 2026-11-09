/**
 * @file supabase/analytics.ts
 * @description Analytics event logging to Supabase.
 */

import { getSupabaseAdmin, isSupabaseConfigured } from "./client";

interface AnalyticsEvent {
  eventType: string;
  metadata?: Record<string, unknown>;
  userId?: string;
  sessionId?: string;
}

/** Log an analytics event. Silently fails if Supabase is unavailable. */
export async function logAnalyticsEvent(event: AnalyticsEvent): Promise<void> {
  if (!isSupabaseConfigured) return;
  try {
    const supabase = getSupabaseAdmin();
    await supabase.from("analytics_events").insert({
      event_type: event.eventType,
      metadata: event.metadata ?? {},
      user_id: event.userId ?? null,
      session_id: event.sessionId ?? null,
      occurred_at: new Date().toISOString(),
    });
  } catch {
    // Non-critical — never throw
  }
}

/** Log a search query and result count. */
export async function logSearch(opts: {
  query: string;
  resultCount: number;
  userId?: string;
}): Promise<void> {
  return logAnalyticsEvent({
    eventType: "search",
    metadata: { query: opts.query, results: opts.resultCount },
    userId: opts.userId,
  });
}

