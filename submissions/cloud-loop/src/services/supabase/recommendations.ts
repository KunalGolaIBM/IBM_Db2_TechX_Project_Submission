/**
 * @file supabase/recommendations.ts
 * @description Personalised recommendations using Supabase analytics history.
 */

import { getSupabaseAdmin, isSupabaseConfigured } from "./client";

export interface Recommendation {
  id: string;
  type: string;
  title: string;
  company?: string;
  applyUrl?: string;
  reason: string;
  score: number;
}

/** Get personalised recommendations for a user based on Supabase analytics. */
export async function getRecommendations(userId?: string, limit = 6): Promise<Recommendation[]> {
  // 1. Try to find user's recent activity from Supabase analytics_events
  let topKeywords: string[] = [];
  if (userId && isSupabaseConfigured) {
    try {
      const supabase = getSupabaseAdmin();
      const { data } = await supabase
        .from("analytics_events")
        .select("metadata")
        .eq("user_id", userId)
        .eq("event_type", "search")
        .order("occurred_at", { ascending: false })
        .limit(10);

      if (data) {
        topKeywords = data
          .map((r) => (r.metadata as Record<string, unknown>)?.query as string)
          .filter(Boolean)
          .slice(0, 5);
      }
    } catch { /* silent */ }
  }

  // 2. Load static data for scoring
  try {
    const [{ jobs }, { internships }, { programs }] = await Promise.all([
      import("@/features/jobs"),
      import("@/features/internships"),
      import("@/features/programs"),
    ]);

    const all = [
      ...jobs.slice(0, 100).map((j) => ({ id: j.id, type: "job", title: j.role, company: j.company, applyUrl: j.applyUrl, text: `${j.role} ${j.company} ${j.skills?.join(" ")}` })),
      ...internships.slice(0, 100).map((i) => ({ id: i.id, type: "internship", title: i.role, company: i.company, applyUrl: i.applyUrl, text: `${i.role} ${i.company} ${i.skills?.join(" ")}` })),
      ...programs.slice(0, 50).map((p) => ({ id: p.id, type: "program", title: p.name, company: p.provider, applyUrl: p.website, text: `${p.name} ${p.provider} ${p.tags?.join(" ")}` })),
    ];

    return all
      .map((item) => {
        let score = 0.5;
        if (topKeywords.length > 0) {
          const haystack = item.text.toLowerCase();
          for (const kw of topKeywords) {
            if (haystack.includes(kw.toLowerCase())) score += 0.15;
          }
        }
        return {
          id: item.id,
          type: item.type,
          title: item.title,
          company: item.company,
          applyUrl: item.applyUrl,
          score,
          reason: topKeywords.length > 0 ? `Based on your interest in "${topKeywords[0]}"` : "Trending on Cloud Loop",
        };
      })
      .sort((a, b) => b.score - a.score)
      .slice(0, limit);
  } catch {
    return [];
  }
}

