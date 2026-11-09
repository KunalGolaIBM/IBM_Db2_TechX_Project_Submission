import { NextRequest, NextResponse } from "next/server";
import { semanticSearch } from "@/services/supabase/search";
import { logSearch } from "@/services/supabase/analytics";

/** POST /api/db2/search — AI semantic search (backed by Supabase) */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as { query?: string; userId?: string };
    const { query, userId } = body;
    if (!query || query.trim().length < 2) {
      return NextResponse.json({ success: false, error: "Query must be at least 2 characters." }, { status: 400 });
    }
    const results = await semanticSearch(query.trim(), userId, 20);
    await logSearch({ query: query.trim(), resultCount: results.length, userId });
    return NextResponse.json({ success: true, data: results, count: results.length });
  } catch (error) {
    const msg = error instanceof Error ? error.message : "Search failed";
    return NextResponse.json({ success: false, error: msg }, { status: 500 });
  }
}
