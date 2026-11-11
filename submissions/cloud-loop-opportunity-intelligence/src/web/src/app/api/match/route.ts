import { NextRequest, NextResponse } from "next/server";
import { matchOpportunities } from "@/services/opportunities";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { skills, interests, year, top_k } = body;

    if (!Array.isArray(skills) || skills.length === 0) {
      return NextResponse.json({ error: "At least one skill is required" }, { status: 400 });
    }

    const result = await matchOpportunities({
      skills,
      interests,
      year,
      top_k: top_k || 10,
    });

    return NextResponse.json(result);
  } catch (err: any) {
    console.error("[API /api/match] Error:", err);
    return NextResponse.json(
      { error: "Matching service failed", details: err.message },
      { status: 500 }
    );
  }
}
