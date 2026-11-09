/**
 * @file recommendations.ts
 * @description Personalised opportunity recommendations based on user search history in Db2.
 */

import { getUserRecentSearches, getOpportunities } from "@/services/db2/queries";

export interface Recommendation {
  id: string;
  type: string;
  title: string;
  company?: string;
  applyUrl?: string;
  reason: string;
  score: number;
}

/**
 * Get personalised recommendations for a user based on their Db2 search history.
 * Falls back to general top listings when no history is available.
 *
 * @param userId - Clerk user ID
 * @param limit - Number of recommendations to return
 */
export async function getPersonalisedRecommendations(
  userId?: string,
  limit = 6
): Promise<Recommendation[]> {
  // 1. Fetch user's recent search terms from Db2
  let topKeywords: string[] = [];
  if (userId) {
    try {
      const { rows } = await getUserRecentSearches(userId, 5);
      topKeywords = rows.map((r) => r.QUERY as string);
    } catch {
      // silent — will fall back to general
    }
  }

  // 2. Fetch opportunities from Db2
  try {
    const { rows } = await getOpportunities({ limit: 200 });
    if (!rows.length) return [];

    const scored = rows
      .map((row) => {
        let score = 0.5; // baseline

        if (topKeywords.length > 0) {
          const haystack = `${row.TITLE} ${row.COMPANY ?? ""} ${row.SKILLS ?? ""}`.toLowerCase();
          for (const kw of topKeywords) {
            if (haystack.includes(kw.toLowerCase())) score += 0.1;
          }
        }

        // Boost recent items
        if (row.CREATED_AT) {
          const ageMs = Date.now() - new Date(row.CREATED_AT as string).getTime();
          const ageDays = ageMs / (1000 * 60 * 60 * 24);
          score += Math.max(0, 0.2 - ageDays * 0.01);
        }

        return {
          id: row.ID as string,
          type: row.TYPE as string,
          title: row.TITLE as string,
          company: row.COMPANY as string | undefined,
          applyUrl: row.APPLY_URL as string | undefined,
          score,
          reason:
            topKeywords.length > 0
              ? `Based on your searches for "${topKeywords[0]}"`
              : "Trending on Cloud Loop",
        };
      })
      .sort((a, b) => b.score - a.score)
      .slice(0, limit);

    return scored;
  } catch {
    return [];
  }
}

