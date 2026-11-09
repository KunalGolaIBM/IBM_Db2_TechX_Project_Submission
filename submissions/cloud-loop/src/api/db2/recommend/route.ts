import { NextRequest, NextResponse } from "next/server";
import { getRecommendations } from "@/services/supabase/recommendations";

/** GET /api/db2/recommend — Personalised recommendations */
export async function GET(req: NextRequest) {
  try {
    const userId = req.nextUrl.searchParams.get("userId") ?? undefined;
    const limit = Math.min(parseInt(req.nextUrl.searchParams.get("limit") ?? "6", 10), 20);
    const data = await getRecommendations(userId, limit);
    return NextResponse.json({ success: true, data });
  } catch (error) {
    const msg = error instanceof Error ? error.message : "Recommendations failed";
    return NextResponse.json({ success: false, error: msg }, { status: 500 });
  }
}
