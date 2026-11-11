import { aiServiceFetch } from "@/services/api/client";

export interface OpportunityItem {
  id: string;
  kind: "job" | "internship" | "event" | "program" | "certification";
  slug: string;
  title: string;
  org: string;
  location?: string | null;
  mode?: string | null;
  deadline?: string | null;
  posted?: string | null;
  apply_url: string;
  source: string;
  skills: string[];
  description?: string | null;
  updated_at?: string;
}

export interface PaginatedOpportunities {
  items: OpportunityItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface SemanticSearchResultItem extends OpportunityItem {
  score: number;
}

export interface SemanticSearchResponse {
  query: string;
  results: SemanticSearchResultItem[];
  total: number;
  kind?: string | null;
}

export interface MatchResultItem {
  opportunity: OpportunityItem;
  match_percentage: number;
  why: string;
  matched_skills: string[];
  explanation_type: "llm" | "deterministic";
}

export interface MatchResponse {
  matches: MatchResultItem[];
  total: number;
  skills_provided: string[];
  mode: string;
}

export async function fetchOpportunities(params?: {
  kind?: string;
  query?: string;
  limit?: number;
  offset?: number;
  active_only?: boolean;
}): Promise<PaginatedOpportunities> {
  return aiServiceFetch<PaginatedOpportunities>("/api/v1/opportunities", {
    method: "GET",
    params,
  });
}

export async function fetchOpportunityBySlug(slug: string): Promise<OpportunityItem> {
  return aiServiceFetch<OpportunityItem>(`/api/v1/opportunities/${encodeURIComponent(slug)}`, {
    method: "GET",
  });
}

export async function semanticSearchOpportunities(
  query: string,
  kind?: string,
  top_k: number = 10
): Promise<SemanticSearchResponse> {
  return aiServiceFetch<SemanticSearchResponse>("/api/v1/search/semantic", {
    method: "POST",
    body: JSON.stringify({ query, kind: kind || null, top_k }),
  });
}

export async function matchOpportunities(payload: {
  skills: string[];
  interests?: string;
  year?: string;
  top_k?: number;
}): Promise<MatchResponse> {
  return aiServiceFetch<MatchResponse>("/api/v1/match", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchStats(): Promise<{
  total_opportunities: number;
  active_opportunities: number;
  by_kind: Record<string, number>;
  closing_within_7_days: number;
  timestamp: string;
}> {
  return aiServiceFetch("/api/v1/stats", {
    method: "GET",
  });
}
