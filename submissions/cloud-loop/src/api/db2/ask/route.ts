import { NextRequest, NextResponse } from "next/server";
import { ragAnswer } from "@/services/ai/rag";

/** POST /api/db2/ask — RAG-based Q&A (backed by Supabase + optional Gemini) */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as { question?: string; userId?: string };
    const { question, userId } = body;
    if (!question || question.trim().length < 3) {
      return NextResponse.json({ success: false, error: "Please enter a question." }, { status: 400 });
    }
    const response = await ragAnswer(question.trim(), userId);
    return NextResponse.json({ success: true, ...response });
  } catch (error) {
    const msg = error instanceof Error ? error.message : "Could not answer question";
    return NextResponse.json({ success: false, error: msg }, { status: 500 });
  }
}
