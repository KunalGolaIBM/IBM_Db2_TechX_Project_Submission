/**
 * Odyssey — suggest-mission Edge Function
 *
 * Single entry point for all Gemini-powered intelligence in the
 * CAPTURE → UNDERSTAND → PLAN → EXECUTE flow.
 *
 * Operations (set via request body `operation` field):
 *   "interpret"       — parse a free-text brain dump into structured tasks
 *   "plan"            — generate three planning approaches from interpreted tasks
 *   "suggest_mission" — generate the first concrete mission for a chosen approach
 *
 * Deploy:
 *   supabase functions deploy suggest-mission --no-verify-jwt
 *
 * Set secret:
 *   supabase secrets set GEMINI_API_KEY=AIza...
 *
 * Model: gemini-flash-latest (fast, low-latency, good instruction following)
 */

import { isValidMissionDuration } from '../_shared/missionDuration.ts';

const CORS_HEADERS = {
  'Access-Control-Allow-Origin':  '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization, apikey, x-client-info',
};

// gemini-3.6-flash — current production model as of Aug 2026.
// gemini-2.5-flash was tried but the API returned 404 for this key.
// The root cause of the previous 502s was markdown-wrapped JSON from Gemini:
const CANDIDATE_MODELS = [
  'gemini-3.6-flash',
  'gemini-3.5-flash',
  'gemini-3.5-flash-lite',
  'gemini-3.1-flash-lite',
  'gemini-flash-latest',
];

// ─── Shared Gemini caller with multi-model fallback ───────────────────────────

async function callGemini(
  apiKey: string,
  prompt: string,
  maxOutputTokens = 1200,
): Promise<{ text: string | null; geminiStatus?: number; geminiError?: string; modelUsed?: string }> {
  let lastStatus = 0;
  let lastError = 'No models tried';

  for (const model of CANDIDATE_MODELS) {
    const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`;
    console.log(`[Gemini] trying ${model}, maxTokens=${maxOutputTokens}, promptLen=${prompt.length}`);

    let res: Response;
    try {
      res = await fetch(`${endpoint}?key=${apiKey}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: AbortSignal.timeout(7000),
        body: JSON.stringify({
          contents: [{ role: 'user', parts: [{ text: prompt }] }],
          generationConfig: {
            responseMimeType: 'application/json',
            maxOutputTokens,
          },
        }),
      });
    } catch (fetchErr) {
      console.error(`[Gemini] ${model} fetch() threw:`, fetchErr);
      lastError = `${model}: ${String(fetchErr)}`;
      continue;
    }

    if (!res.ok) {
      const errText = await res.text();
      console.error(`[Gemini] ${model} HTTP ${res.status}:`, errText.slice(0, 300));
      lastStatus = res.status;
      lastError = `${model} (HTTP ${res.status}): ${errText.slice(0, 150)}`;
      // If 429 quota/rate limit or 503 or 404, fallback to next model immediately
      continue;
    }

    const data = await res.json() as {
      candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }>;
      error?: { message?: string; code?: number };
    };

    if (data?.error) {
      console.error(`[Gemini] ${model} API-level error:`, JSON.stringify(data.error));
      lastStatus = 200;
      lastError = `${model}: ${JSON.stringify(data.error)}`;
      continue;
    }

    const raw = data?.candidates?.[0]?.content?.parts?.[0]?.text ?? null;
    if (!raw) {
      console.error(`[Gemini] ${model} no text in response:`, JSON.stringify(data).slice(0, 300));
      lastStatus = 200;
      lastError = `${model}: no_text_in_response`;
      continue;
    }

    console.log(`[Gemini] success with ${model}, rawLen=${raw.length}, rawPreview=${raw.slice(0, 120).replace(/\n/g, '\\n')}`);

    // Robust JSON extraction: strip any markdown fencing and find the outermost { } or [ ] pair.
    const stripped = raw
      .replace(/^```json\s*/im, '')
      .replace(/^```\s*/im, '')
      .replace(/```\s*$/im, '')
      .trim();

    // Find first { or [ and its matching closing bracket
    const firstBrace   = stripped.indexOf('{');
    const firstBracket = stripped.indexOf('[');
    const start = (firstBrace === -1) ? firstBracket
                : (firstBracket === -1) ? firstBrace
                : Math.min(firstBrace, firstBracket);

    if (start === -1) {
      console.error(`[Gemini] ${model} no JSON object found. raw:`, raw.slice(0, 300));
      lastStatus = 200;
      lastError = `${model}: no_json_in_response: ${raw.slice(0, 150)}`;
      continue;
    }

    const openChar  = stripped[start];
    const closeChar = openChar === '{' ? '}' : ']';
    const lastClose = stripped.lastIndexOf(closeChar);

    if (lastClose === -1 || lastClose <= start) {
      console.error(`[Gemini] ${model} unmatched brackets. raw:`, raw.slice(0, 300));
      lastStatus = 200;
      lastError = `${model}: unmatched_brackets: ${raw.slice(0, 150)}`;
      continue;
    }

    const cleaned = stripped.slice(start, lastClose + 1);
    return { text: cleaned, geminiStatus: 200, modelUsed: model };
  }

  return { text: null, geminiStatus: lastStatus, geminiError: lastError };
}

// ─── OPERATION: interpret ─────────────────────────────────────────────────────

interface InterpretRequest {
  raw_input:          string;
  available_hours:    number;
  energy:             string;
  consistency_goals:  string[];
  horizon:            string;
  current_date_iso:   string;     // e.g. "2026-08-26T14:30:00+08:00"
  current_date_label: string;     // e.g. "Wednesday, 26 August 2026"
}

function buildInterpretPrompt(r: InterpretRequest): string {
  const goals = r.consistency_goals.length > 0
    ? r.consistency_goals.join(', ')
    : 'none specified';

  return `
You are Odyssey, a focused personal execution assistant.
Today is ${r.current_date_label} (ISO: ${r.current_date_iso}).

The user has captured the following (raw brain dump):
"${r.raw_input}"

Additional context the user provided:
- Available time today: ${r.available_hours} hours
- Energy level: ${r.energy}
- Ongoing consistency goals: ${goals}
- Planning horizon: ${r.horizon}

Your task: parse the brain dump into a structured list of tasks, commitments, and goals.

IMPORTANT RULES:
1. Identify each distinct task, assignment, submission, or goal — even if expressed informally.
2. Resolve ALL deadline expressions relative to today (${r.current_date_label}):
   - "tonight" = today (${r.current_date_iso.slice(0,10)}) late evening
   - "tomorrow" = next calendar day
   - "Friday", "Monday", etc. = nearest upcoming occurrence of that weekday
   - "30 Aug", "Aug 30", "30/08", "August 30" = literal date (infer year = current year unless past)
   - "in 3 days" = 3 days from today
   - Never hallucinate a deadline if the user did not supply one.
3. For category:
   - "deadline" = has a deadline within 7 days
   - "upcoming" = has a deadline 8+ days away
   - "goal" = ongoing habit or consistency practice (no single deadline)
   - "task" = discrete action with no stated deadline
4. For priority:
   - "urgent" = tonight / today deadline, or user used urgent language
   - "high" = tomorrow or strong importance signals
   - "medium" = this week
   - "low" = beyond this week, or a habit/goal
5. isConsistency = true only for habits/ongoing practices the user explicitly wants to maintain.
6. If something is ambiguous (unclear deadline, unclear scope), set ambiguity to a short note.
7. Consistency goals from the structured field should appear as items with isConsistency: true.

Return ONLY valid JSON — no markdown, no explanation:
{
  "items": [
    {
      "text": "string — clean task title, no deadline phrases",
      "category": "deadline | upcoming | goal | task",
      "deadlineLabel": "human-readable string e.g. 'Tonight · Aug 26' or null",
      "isoDeadline": "YYYY-MM-DD or null",
      "priority": "urgent | high | medium | low",
      "isConsistency": false,
      "ambiguity": "string or null"
    }
  ]
}
`.trim();
}

// ─── OPERATION: plan ──────────────────────────────────────────────────────────

interface PlanRequest {
  raw_input:         string;
  available_hours:   number;
  energy:            string;
  consistency_goals: string[];
  horizon:           string;
  current_date_label: string;
  items: Array<{
    text:          string;
    category:      string;
    deadlineLabel: string | null;
    isoDeadline:   string | null;
    priority:      string;
    isConsistency: boolean;
  }>;
}

function buildPlanPrompt(r: PlanRequest): string {
  const itemsJson = JSON.stringify(r.items, null, 2);
  const goals = r.consistency_goals.length > 0
    ? r.consistency_goals.join(', ')
    : 'none';

  return `
You are Odyssey, a focused personal execution assistant.
Today is ${r.current_date_label}.

The user has ${r.available_hours} hours available today and their energy is ${r.energy}.
Original brain dump: "${r.raw_input}"
Consistency goals: ${goals}
Planning horizon: ${r.horizon}

Interpreted tasks:
${itemsJson}

Generate exactly THREE planning approaches using these SAME tasks — do NOT invent new tasks.
The approaches differ in prioritization, sequencing, and emphasis — not in what tasks exist.

Approach A: "Deadline Focus" — tackle the most imminent/urgent deadlines first. Protect deadline commitments above all else.
Approach B: "Balanced" — distribute effort across deadlines, upcoming work, and consistency goals. No single concern dominates.
Approach C: "Consistency Focus" — protect ongoing habits and consistency goals while still honouring imminent deadlines.

For EACH approach, provide:
- A clear rationale for why this approach fits the user's current context (energy, hours, deadlines)
- An ordered list of the tasks (all tasks appear in each approach, just in different order/framing)
- Realistic time estimate given ${r.available_hours}h available
- The key tradeoff this approach makes

Return ONLY valid JSON — no markdown, no explanation:
{
  "plans": [
    {
      "id": "deadline",
      "emoji": "⚡",
      "name": "Deadline Focus",
      "tagline": "one compelling short sentence",
      "whyThisApproach": "2-3 sentences — why this fits the user's actual situation today",
      "orderedItems": [
        {
          "text": "task title",
          "deadlineLabel": "string or null",
          "priority": "urgent | high | medium | low",
          "rationale": "one sentence — why this item is placed here in this approach"
        }
      ],
      "timeEstimate": "e.g. '~3.5 of your 4 hours on deadline work'",
      "tradeoff": "one sentence — what this approach sacrifices or defers"
    },
    {
      "id": "balanced",
      "emoji": "⚖️",
      "name": "Balanced",
      ...same structure...
    },
    {
      "id": "consistency",
      "emoji": "🌱",
      "name": "Consistency Focus",
      ...same structure...
    }
  ]
}
`.trim();
}

// ─── OPERATION: suggest_mission ───────────────────────────────────────────────

interface SuggestMissionRequest {
  raw_input:          string;
  available_hours:    number;
  energy:             string;
  current_date_label: string;
  selected_plan_id:   string;
  selected_plan_name: string;
  selected_plan_why:  string;
  first_item_text:    string;
  first_item_deadline: string | null;
  all_items_summary:  string;
}

function buildSuggestMissionPrompt(r: SuggestMissionRequest): string {
  return `
You are Odyssey, a focused personal execution assistant.
Today is ${r.current_date_label}.
The user has ${r.available_hours} hours available and energy is ${r.energy}.

Original brain dump: "${r.raw_input}"
All tasks in context: ${r.all_items_summary}

The user chose the "${r.selected_plan_name}" approach.
Why this approach fits: ${r.selected_plan_why}

The first recommended task for this approach is: "${r.first_item_text}"${r.first_item_deadline ? ` (deadline: ${r.first_item_deadline})` : ''}.

Create a concrete, focused mission for this first task. The mission must be:
- Realistic given ${r.available_hours}h available and ${r.energy} energy
- Specific enough that the user knows exactly what to do
- Completable in one focused session

Return ONLY valid JSON — no markdown, no explanation:
{
  "title": "short energetic mission title, max 8 words, no trailing period",
  "objective": "one sentence — what does success look like, max 20 words",
  "next_action": "the single most concrete first physical action, max 15 words, start with a verb",
  "planned_minutes": 25 or 30 or 45 or 50 or 60 or 90,
  "reasoning": "1-2 sentences explaining why this specific mission makes sense right now given context"
}
`.trim();
}

// ─── Validators ───────────────────────────────────────────────────────────────

function validateInterpretation(parsed: unknown): boolean {
  if (typeof parsed !== 'object' || parsed === null) return false;
  const p = parsed as Record<string, unknown>;
  if (!Array.isArray(p.items)) return false;
  return p.items.every((item: unknown) => {
    if (typeof item !== 'object' || item === null) return false;
    const i = item as Record<string, unknown>;
    return (
      typeof i.text === 'string' && i.text.trim() &&
      ['deadline', 'upcoming', 'goal', 'task'].includes(i.category as string) &&
      ['urgent', 'high', 'medium', 'low'].includes(i.priority as string) &&
      typeof i.isConsistency === 'boolean'
    );
  });
}

function validatePlans(parsed: unknown, expectedItems: PlanRequest['items']): boolean {
  if (typeof parsed !== 'object' || parsed === null) return false;
  const p = parsed as Record<string, unknown>;
  if (!Array.isArray(p.plans) || p.plans.length !== 3) return false;

  const expectedIds = new Set(['deadline', 'balanced', 'consistency']);
  const expectedTaskTexts = new Set(expectedItems.map((item) => item.text.trim()));
  const seenPlanIds = new Set<string>();

  return p.plans.every((plan: unknown) => {
    if (typeof plan !== 'object' || plan === null) return false;
    const pl = plan as Record<string, unknown>;
    const id = pl.id as string;
    if (!expectedIds.has(id) || seenPlanIds.has(id)) return false;
    seenPlanIds.add(id);

    if (
      typeof pl.name !== 'string' || !pl.name.trim() ||
      typeof pl.tagline !== 'string' || !pl.tagline.trim() ||
      typeof pl.whyThisApproach !== 'string' || !pl.whyThisApproach.trim() ||
      typeof pl.timeEstimate !== 'string' || !pl.timeEstimate.trim() ||
      typeof pl.tradeoff !== 'string' || !pl.tradeoff.trim() ||
      !Array.isArray(pl.orderedItems)
    ) return false;

    const orderedItems = pl.orderedItems as unknown[];
    if (orderedItems.length !== expectedTaskTexts.size) return false;
    const seenTasks = new Set<string>();

    for (const item of orderedItems) {
      if (typeof item !== 'object' || item === null) return false;
      const entry = item as Record<string, unknown>;
      if (
        typeof entry.text !== 'string' || !entry.text.trim() ||
        typeof entry.rationale !== 'string' || !entry.rationale.trim() ||
        !['urgent', 'high', 'medium', 'low'].includes(entry.priority as string)
      ) return false;

      const taskText = entry.text.trim();
      if (!expectedTaskTexts.has(taskText) || seenTasks.has(taskText)) return false;
      seenTasks.add(taskText);
    }

    return seenTasks.size === expectedTaskTexts.size;
  }) && seenPlanIds.size === expectedIds.size;
}

function validateMission(parsed: unknown): boolean {
  if (typeof parsed !== 'object' || parsed === null) return false;
  const p = parsed as Record<string, unknown>;
  return (
    typeof p.title === 'string' && (p.title as string).trim().length > 0 &&
    typeof p.objective === 'string' && (p.objective as string).trim().length > 0 &&
    typeof p.next_action === 'string' && (p.next_action as string).trim().length > 0 &&
    isValidMissionDuration(p.planned_minutes) &&
    typeof p.reasoning === 'string'
  );
}

// ─── Main handler ─────────────────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: CORS_HEADERS });
  }

  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
    });
  }

  const apiKey = Deno.env.get('GEMINI_API_KEY');
  if (!apiKey) {
    console.error('[suggest-mission] GEMINI_API_KEY secret is not set');
    return new Response(JSON.stringify({ error: 'GEMINI_API_KEY not configured' }), {
      status: 503, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
    });
  }

  let body: Record<string, unknown>;
  try {
    body = await req.json() as Record<string, unknown>;
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid JSON body' }), {
      status: 400, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
    });
  }

  const operation = body.operation as string | undefined;
  console.log(`[suggest-mission] operation="${operation}", apiKeyPresent=${!!apiKey}`);

  // ── INTERPRET ──────────────────────────────────────────────────────────────
  if (operation === 'interpret') {
    const r = body as unknown as InterpretRequest;
    if (!r.raw_input?.trim()) {
      return new Response(JSON.stringify({ error: 'raw_input required' }), {
        status: 400, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }

    console.log('[interpret] Starting Gemini call, raw_input length:', r.raw_input.length);
    const result = await callGemini(apiKey, buildInterpretPrompt(r), 1200);
    if (!result.text) {
      return new Response(JSON.stringify({ error: 'Gemini unavailable', model: GEMINI_MODEL, geminiStatus: result.geminiStatus, geminiError: result.geminiError }), {
        status: 502, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }
    const raw = result.text;

    let parsed: unknown;
    try { parsed = JSON.parse(raw); } catch (parseErr) {
      console.error('[interpret] parse fail. rawPreview:', raw.slice(0, 300));
      return new Response(JSON.stringify({ error: 'Parse failed', rawPreview: raw.slice(0, 200) }), {
        status: 502, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }

    if (!validateInterpretation(parsed)) {
      console.error('interpret validation fail:', JSON.stringify(parsed).slice(0, 200));
      return new Response(JSON.stringify({ error: 'Invalid interpretation shape' }), {
        status: 502, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }

    return new Response(JSON.stringify(parsed), {
      status: 200, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
    });
  }

  // ── PLAN ───────────────────────────────────────────────────────────────────
  if (operation === 'plan') {
    const r = body as unknown as PlanRequest;
    if (!Array.isArray(r.items) || r.items.length === 0) {
      return new Response(JSON.stringify({ error: 'items required' }), {
        status: 400, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }

    const resultPlan = await callGemini(apiKey, buildPlanPrompt(r), 2400);
    if (!resultPlan.text) {
      return new Response(JSON.stringify({ error: 'Gemini unavailable', model: GEMINI_MODEL, geminiStatus: resultPlan.geminiStatus, geminiError: resultPlan.geminiError }), {
        status: 502, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }
    const raw = resultPlan.text;

    let parsed: unknown;
    try { parsed = JSON.parse(raw); } catch (parseErr) {
      console.error('[plan] parse fail. rawPreview:', raw.slice(0, 300));
      return new Response(JSON.stringify({ error: 'Parse failed', rawPreview: raw.slice(0, 200) }), {
        status: 502, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }

    if (!validatePlans(parsed, r.items)) {
      console.error('plan validation fail:', JSON.stringify(parsed).slice(0, 200));
      return new Response(JSON.stringify({ error: 'Invalid or incomplete plans: each approach must include every input task exactly once with valid fields.' }), {
        status: 502, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }

    return new Response(JSON.stringify(parsed), {
      status: 200, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
    });
  }

  // ── SUGGEST_MISSION ────────────────────────────────────────────────────────
  if (operation === 'suggest_mission') {
    const r = body as unknown as SuggestMissionRequest;
    if (!r.first_item_text?.trim()) {
      return new Response(JSON.stringify({ error: 'first_item_text required' }), {
        status: 400, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }

    const resultMission = await callGemini(apiKey, buildSuggestMissionPrompt(r), 400);
    if (!resultMission.text) {
      return new Response(JSON.stringify({ error: 'Gemini unavailable', model: GEMINI_MODEL, geminiStatus: resultMission.geminiStatus, geminiError: resultMission.geminiError }), {
        status: 502, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }
    const raw = resultMission.text;

    let parsed: unknown;
    try { parsed = JSON.parse(raw); } catch (parseErr) {
      console.error('[mission] parse fail. rawPreview:', raw.slice(0, 300));
      return new Response(JSON.stringify({ error: 'Parse failed', rawPreview: raw.slice(0, 200) }), {
        status: 502, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }

    if (!validateMission(parsed)) {
      console.error('mission validation fail:', JSON.stringify(parsed).slice(0, 200));
      return new Response(JSON.stringify({ error: 'Invalid mission: required text fields must be non-empty and planned_minutes must be a whole number from 1 to 240.' }), {
        status: 502, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }

    const m = parsed as Record<string, unknown>;
    return new Response(JSON.stringify({
      title:           (m.title as string).trim(),
      objective:       (m.objective as string).trim(),
      next_action:     (m.next_action as string).trim(),
      planned_minutes: m.planned_minutes,
      reasoning:       (m.reasoning as string).trim(),
    }), {
      status: 200, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
    });
  }

  if (operation === 'list_models') {
    try {
      const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey}`);
      const data = await res.json();
      return new Response(JSON.stringify(data), {
        status: res.status, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    } catch (err) {
      return new Response(JSON.stringify({ error: String(err) }), {
        status: 500, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
      });
    }
  }

  return new Response(JSON.stringify({ error: `Unknown operation: ${operation ?? '(none)'}` }), {
    status: 400, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
  });
});
