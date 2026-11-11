import { NextRequest, NextResponse } from "next/server";
import { fetchUserTracking, updateUserTracking } from "@/services/tracking";
import { auth } from "@clerk/nextjs/server";

export async function GET(req: NextRequest) {
  try {
    let userId: string | null = null;

    if (process.env.AUTH_MODE === "demo") {
      userId = "demo-user-123";
    } else {
      const clerkAuth = await auth();
      userId = clerkAuth.userId;
    }

    if (!userId) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const tracked = await fetchUserTracking(userId);
    return NextResponse.json(tracked);
  } catch (err: any) {
    console.error("[API /api/tracking] GET Error:", err);
    return NextResponse.json(
      { error: "Failed to fetch user tracking data", details: err.message },
      { status: 500 }
    );
  }
}

export async function PUT(req: NextRequest) {
  try {
    let userId: string | null = null;

    if (process.env.AUTH_MODE === "demo") {
      userId = "demo-user-123";
    } else {
      const clerkAuth = await auth();
      userId = clerkAuth.userId;
    }

    if (!userId) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const body = await req.json();
    const { opportunity_id, status, bookmarked } = body;

    if (!opportunity_id) {
      return NextResponse.json({ error: "opportunity_id is required" }, { status: 400 });
    }

    const updated = await updateUserTracking(userId, {
      opportunity_id,
      status,
      bookmarked,
    });

    return NextResponse.json(updated);
  } catch (err: any) {
    console.error("[API /api/tracking] PUT Error:", err);
    return NextResponse.json(
      { error: "Failed to update tracking status", details: err.message },
      { status: 500 }
    );
  }
}
