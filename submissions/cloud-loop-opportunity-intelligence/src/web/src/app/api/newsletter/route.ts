import { NextRequest, NextResponse } from "next/server";
import { subscribeNewsletter } from "@/services/newsletter";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { email } = body;

    if (!email || typeof email !== "string" || !email.includes("@")) {
      return NextResponse.json({ error: "Valid email address is required" }, { status: 400 });
    }

    const result = await subscribeNewsletter(email.trim().toLowerCase());
    return NextResponse.json(result);
  } catch (err: any) {
    console.error("[API /api/newsletter] Error:", err);
    return NextResponse.json(
      { error: "Newsletter subscription failed", details: err.message },
      { status: 500 }
    );
  }
}
