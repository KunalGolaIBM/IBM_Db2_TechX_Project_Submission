import { NextRequest, NextResponse } from "next/server";
import { fetchStats } from "@/services/opportunities";

export async function GET(_req: NextRequest) {
  try {
    const stats = await fetchStats();
    return NextResponse.json(stats);
  } catch (err: any) {
    console.error("[API /api/stats] Error:", err);
    return NextResponse.json(
      { error: "Failed to fetch stats", details: err.message },
      { status: 500 }
    );
  }
}
