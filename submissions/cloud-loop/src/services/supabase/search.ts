/**
 * @file supabase/search.ts
 * @description AI-powered semantic search using Supabase as the vector store.
 * Uses bag-of-words TF similarity over in-memory data fetched from Supabase,
 * with a keyword fallback when the table is not set up.
 */

import { getSupabaseAdmin, isSupabaseConfigured } from "./client";
import { logAnalyticsEvent } from "./analytics";

export interface SearchResult {
  id: string;
  type: string;
  title: string;
  company?: string;
  location?: string;
  skills?: string[];
  applyUrl?: string;
  deadline?: string;
  score: number;
  source: "supabase_semantic" | "supabase_keyword" | "static";
}

/** Simple bag-of-words embedding (128-dim float vector, no API key needed) */
function simpleEmbed(text: string): number[] {
  const words = text.toLowerCase().replace(/[^a-z0-9 ]/g, "").split(/\s+/).filter(Boolean);
  const dim = 128;
  const vec = new Array<number>(dim).fill(0);
  for (const word of words) {
    let h = 0;
    for (let i = 0; i < word.length; i++) h = (h * 31 + word.charCodeAt(i)) & 0x7fffffff;
    vec[h % dim] += 1;
  }
  const norm = Math.sqrt(vec.reduce((s, v) => s + v * v, 0)) || 1;
  return vec.map((v) => v / norm);
}

function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length) return 0;
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) { dot += a[i] * b[i]; na += a[i] ** 2; nb += b[i] ** 2; }
  return na && nb ? dot / (Math.sqrt(na) * Math.sqrt(nb)) : 0;
}

/**
 * Semantic search over tracked_opportunities in Supabase.
 * Falls back to in-memory static data keyword match if table doesn't exist.
 */
export async function semanticSearch(
  query: string,
  userId?: string,
  limit = 20
): Promise<SearchResult[]> {
  const queryVec = simpleEmbed(query);

  if (isSupabaseConfigured) {
    try {
      const supabase = getSupabaseAdmin();
      // Try the tracked_opportunities table first (created by existing migration)
      const { data, error } = await supabase
        .from("tracked_opportunities")
        .select("id, type, title, company, location, skills, apply_url, deadline, description")
        .or(`title.ilike.%${query}%,company.ilike.%${query}%,description.ilike.%${query}%`)
        .limit(limit * 3);

      if (!error && data && data.length > 0) {
        const scored = data
          .map((row) => {
            const text = `${row.title ?? ""} ${row.company ?? ""} ${row.description ?? ""} ${Array.isArray(row.skills) ? row.skills.join(" ") : ""}`;
            const vec = simpleEmbed(text);
            const score = cosineSimilarity(queryVec, vec);
            return { row, score };
          })
          .sort((a, b) => b.score - a.score)
          .slice(0, limit);

        await logAnalyticsEvent({ eventType: "ai_search", metadata: { query, results: scored.length }, userId });

        return scored.map(({ row, score }) => ({
          id: String(row.id),
          type: String(row.type ?? "opportunity"),
          title: String(row.title),
          company: row.company ? String(row.company) : undefined,
          location: row.location ? String(row.location) : undefined,
          skills: Array.isArray(row.skills) ? row.skills : [],
          applyUrl: row.apply_url ? String(row.apply_url) : undefined,
          deadline: row.deadline ? String(row.deadline) : undefined,
          score,
          source: "supabase_semantic",
        }));
      }

      // Try opportunities table as fallback
      const { data: oppData } = await supabase
        .from("opportunities")
        .select("*")
        .or(`title.ilike.%${query}%,company.ilike.%${query}%`)
        .limit(limit);

      if (oppData && oppData.length > 0) {
        return oppData.map((row) => ({
          id: String(row.id ?? row.slug ?? Math.random()),
          type: String(row.type ?? "opportunity"),
          title: String(row.title ?? row.role ?? "Opportunity"),
          company: row.company ? String(row.company) : undefined,
          location: row.location ? String(row.location) : undefined,
          skills: Array.isArray(row.skills) ? row.skills : [],
          applyUrl: row.apply_url ?? row.applyUrl,
          deadline: row.deadline,
          score: 0.6,
          source: "supabase_keyword",
        }));
      }
    } catch (err) {
      console.warn("[SemanticSearch] Supabase query failed:", err);
    }
  }

  // Final fallback: in-memory static data
  return staticKeywordSearch(query, queryVec, limit);
}

/** In-memory keyword + vector search over statically imported data */
async function staticKeywordSearch(query: string, queryVec: number[], limit: number): Promise<SearchResult[]> {
  try {
    const [
      { jobs },
      { internships },
      { events },
      { programs },
    ] = await Promise.all([
      import("@/features/jobs"),
      import("@/features/internships"),
      import("@/features/events"),
      import("@/features/programs"),
    ]);

    const all = [
      ...jobs.map((j) => ({ ...j, _type: "job", _title: j.role, _co: j.company })),
      ...internships.map((i) => ({ ...i, _type: "internship", _title: i.role, _co: i.company })),
      ...events.map((e) => ({ ...e, _type: "event", _title: e.title, _co: e.organizer })),
      ...programs.map((p) => ({ ...p, _type: "program", _title: p.name, _co: p.provider })),
    ] as Record<string, unknown>[];

    return all
      .map((item) => {
        const text = `${item._title ?? ""} ${item._co ?? ""} ${item.description ?? ""} ${Array.isArray(item.skills) ? (item.skills as string[]).join(" ") : ""}`;
        const vec = simpleEmbed(text);
        return { item, score: cosineSimilarity(queryVec, vec) };
      })
      .filter(({ score }) => score > 0.05)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
      .map(({ item, score }) => ({
        id: String(item.id ?? item.slug),
        type: String(item._type),
        title: String(item._title ?? "Opportunity"),
        company: item._co ? String(item._co) : undefined,
        location: item.location ? String(item.location) : undefined,
        skills: Array.isArray(item.skills) ? (item.skills as string[]) : [],
        applyUrl: item.applyUrl ? String(item.applyUrl) : undefined,
        deadline: item.deadline ? String(item.deadline) : undefined,
        score,
        source: "static" as const,
      }));
  } catch {
    return [];
  }
}

/** Export embed utility for use in sync operations */
export function embedText(text: string): number[] {
  return simpleEmbed(text);
}

