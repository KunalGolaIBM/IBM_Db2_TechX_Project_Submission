import { NextRequest, NextResponse } from "next/server";
import { semanticSearchOpportunities } from "@/services/opportunities";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { query, kind, top_k } = body;

    if (!query || typeof query !== "string") {
      return NextResponse.json({ error: "Query string is required" }, { status: 400 });
    }

    const result = await semanticSearchOpportunities(query, kind, top_k || 10);
    return NextResponse.json(result);
  } catch (err: any) {
    console.error("[API /api/search] Error:", err);
    return NextResponse.json(
      { error: "Semantic search failed", details: err.message },
      { status: 500 }
    );
  }
}
