/**
 * @file search.ts
 * @description AI-powered semantic search using cosine similarity of text embeddings.
 * Falls back to keyword search when AI is unavailable.
 */

import { keywordSearchOpportunities, logUserSearch } from "@/services/db2/queries";
import { logAnalyticsEvent } from "@/services/db2/queries";

/** Cosine similarity between two float vectors */
function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length) return 0;
  let dot = 0, normA = 0, normB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  if (normA === 0 || normB === 0) return 0;
  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}

/**
 * Simple bag-of-words TF embedding (no external API required).
 * Returns a 128-dim float array representing word frequency.
 */
function simpleEmbed(text: string): number[] {
  const words = text.toLowerCase().replace(/[^a-z0-9 ]/g, "").split(/\s+/).filter(Boolean);
  const vocab: Record<string, number> = {};
  for (const w of words) vocab[w] = (vocab[w] ?? 0) + 1;
  const dim = 128;
  const vec = new Array<number>(dim).fill(0);
  for (const [word, freq] of Object.entries(vocab)) {
    let h = 0;
    for (let i = 0; i < word.length; i++) h = (h * 31 + word.charCodeAt(i)) & 0x7fffffff;
    vec[h % dim] += freq;
  }
  // L2-normalise
  const norm = Math.sqrt(vec.reduce((s, v) => s + v * v, 0)) || 1;
  return vec.map((v) => v / norm);
}

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
  source: "db2_semantic" | "db2_keyword" | "static";
}

/**
 * Perform semantic search over Db2-stored opportunities.
 * Uses local TF embedding + cosine similarity scoring.
 * Falls back to keyword search when no embeddings are stored.
 *
 * @param query - Natural language search string
 * @param userId - Optional user ID for analytics logging
 * @param limit - Maximum results to return
 */
export async function semanticSearch(
  query: string,
  userId?: string,
  limit = 20
): Promise<SearchResult[]> {
  const queryVec = simpleEmbed(query);

  // Try Db2 semantic search first
  try {
    const { getOpportunities } = await import("@/services/db2/queries");
    const { rows } = await getOpportunities({ limit: 500 });

    if (rows.length > 0) {
      const scored = rows
        .map((row) => {
          let score = 0;
          if (row.EMBEDDING) {
            try {
              const storedVec = JSON.parse(row.EMBEDDING as string) as number[];
              score = cosineSimilarity(queryVec, storedVec);
            } catch {
              score = 0;
            }
          }
          return { row, score };
        })
        .filter(({ score }) => score > 0.1)
        .sort((a, b) => b.score - a.score)
        .slice(0, limit);

      if (scored.length > 0) {
        await logUserSearch({ userId, query, resultCount: scored.length });
        await logAnalyticsEvent({ eventType: "ai_search", metadata: { query, results: scored.length }, userId });
        return scored.map(({ row, score }) => ({
          id: row.ID as string,
          type: row.TYPE as string,
          title: row.TITLE as string,
          company: row.COMPANY as string | undefined,
          location: row.LOCATION as string | undefined,
          skills: row.SKILLS ? JSON.parse(row.SKILLS as string) : [],
          applyUrl: row.APPLY_URL as string | undefined,
          deadline: row.DEADLINE as string | undefined,
          score,
          source: "db2_semantic",
        }));
      }
    }
  } catch (err) {
    console.warn("[SemanticSearch] Db2 search failed, falling back to keyword:", err);
  }

  // Fallback: keyword search in Db2
  try {
    const { rows } = await keywordSearchOpportunities(query, limit);
    await logUserSearch({ userId, query, resultCount: rows.length });
    return rows.map((row) => ({
      id: row.ID as string,
      type: row.TYPE as string,
      title: row.TITLE as string,
      company: row.COMPANY as string | undefined,
      location: row.LOCATION as string | undefined,
      skills: row.SKILLS ? JSON.parse(row.SKILLS as string) : [],
      applyUrl: row.APPLY_URL as string | undefined,
      deadline: row.DEADLINE as string | undefined,
      score: 0.5,
      source: "db2_keyword",
    }));
  } catch {
    return [];
  }
}

/** Embed text and return JSON string for Db2 storage. */
export function embedText(text: string): string {
  return JSON.stringify(simpleEmbed(text));
}

