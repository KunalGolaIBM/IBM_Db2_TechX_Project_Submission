/**
 * @file rag.ts (Supabase-backed)
 * @description RAG pipeline — retrieves context from Supabase, generates answers.
 * Uses Google Gemini (free) if GOOGLE_AI_API_KEY is set, otherwise deterministic fallback.
 */

import { semanticSearch } from "@/services/supabase/search";
import { logAnalyticsEvent } from "@/services/supabase/analytics";
import { aiConfig } from "@/config/env";

export interface RagResponse {
  answer: string;
  sources: Array<{ id: string; title: string; type: string; applyUrl?: string }>;
  provider: string;
}

export async function ragAnswer(question: string, userId?: string): Promise<RagResponse> {
  // 1. Retrieve context from Supabase/static data
  const results = await semanticSearch(question, userId, 8);
  const sources = results.slice(0, 5).map((r) => ({
    id: r.id, title: r.title, type: r.type, applyUrl: r.applyUrl,
  }));

  const context = results.length
    ? results.map((r, i) => `[${i + 1}] ${r.title}${r.company ? ` at ${r.company}` : ""} (${r.type}) | ${r.location ?? "India"} | Deadline: ${r.deadline ?? "Open"} | Skills: ${r.skills?.join(", ") ?? "Various"}`).join("\n")
    : "No specific matches found — suggest browsing all sections.";

  const systemPrompt = `You are Cloud Loop's helpful AI assistant. Cloud Loop aggregates student opportunities — jobs, internships, hackathons, programs, and certifications for Indian students. Answer based on the retrieved data below. Be concise, friendly, and encouraging.

Retrieved Opportunities:
${context}`;

  // 2. Try Google Gemini (free tier, no card required)
  if (aiConfig.googleAiKey) {
    try {
      const res = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${aiConfig.googleAiKey}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            contents: [{ role: "user", parts: [{ text: `${systemPrompt}\n\nQuestion: ${question}` }] }],
            generationConfig: { maxOutputTokens: 400, temperature: 0.4 },
          }),
        }
      );
      const data = await res.json() as { candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }> };
      const answer = data?.candidates?.[0]?.content?.parts?.[0]?.text;
      if (answer) {
        await logAnalyticsEvent({ eventType: "ai_query", metadata: { question, provider: "gemini" }, userId });
        return { answer, sources, provider: "gemini" };
      }
    } catch (err) {
      console.warn("[RAG] Gemini failed:", err);
    }
  }

  // 3. Deterministic fallback (always works, no API key)
  await logAnalyticsEvent({ eventType: "ai_query", metadata: { question, provider: "local" }, userId });
  return { answer: buildFallbackAnswer(question, results), sources, provider: "local" };
}

function buildFallbackAnswer(question: string, results: { title: string; company?: string; type: string; applyUrl?: string }[]): string {
  if (!results.length) {
    return `I searched Cloud Loop for "${question}" but didn't find specific matches right now. Try browsing **Jobs**, **Internships**, **Events**, or **Programs** — we update listings daily! 🚀`;
  }
  const list = results.slice(0, 4).map((r) => `• **${r.title}**${r.company ? ` at ${r.company}` : ""} _(${r.type})_`).join("\n");
  return `Here are some opportunities matching **"${question}"**:\n\n${list}\n\nFind full details and apply links on Cloud Loop. Good luck! 💪`;
}
