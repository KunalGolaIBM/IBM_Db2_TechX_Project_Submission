import { NextRequest, NextResponse } from "next/server";
import { fetchOpportunities } from "@/services/opportunities";

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const kind = searchParams.get("kind") || undefined;
    const query = searchParams.get("query") || undefined;
    const limit = searchParams.get("limit") ? parseInt(searchParams.get("limit")!, 10) : 50;
    const offset = searchParams.get("offset") ? parseInt(searchParams.get("offset")!, 10) : 0;
    const active_only = searchParams.get("active_only") === "true";

    const result = await fetchOpportunities({
      kind,
      query,
      limit,
      offset,
      active_only,
    });

    return NextResponse.json(result);
  } catch (err: any) {
    console.error("[API /api/opportunities] Error:", err);
    return NextResponse.json(
      { error: "Failed to fetch opportunities from AI service", details: err.message },
      { status: 500 }
    );
  }
}
