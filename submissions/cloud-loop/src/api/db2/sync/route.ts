import { NextResponse } from "next/server";
import { upsertOpportunity } from "@/services/db2/queries";
import { embedText } from "@/services/ai/search";
import { db2Config } from "@/config/env";

/** POST /api/db2/sync — Sync scraped JSON opportunities into IBM Db2 */
export async function POST() {
  if (!db2Config.isConfigured) {
    return NextResponse.json({
      success: false,
      error: "IBM Db2 is not configured. Set DB2_HOSTNAME, DB2_UID, DB2_PWD in .env.local",
    }, { status: 503 });
  }

  try {
    const [
      { default: jobs },
      { default: internships },
      { default: events },
    ] = await Promise.all([
      import("@/features/jobs/data/scraped-jobs.json"),
      import("@/features/internships/data/scraped-internships.json"),
      import("@/features/events/data/scraped-events.json"),
    ]);

    let synced = 0;
    const allItems = [
      ...((jobs as Record<string, unknown>[]) ?? []).map((j) => ({ ...j, _type: "job" })),
      ...((internships as Record<string, unknown>[]) ?? []).map((i) => ({ ...i, _type: "internship" })),
      ...((events as Record<string, unknown>[]) ?? []).map((e) => ({ ...e, _type: "event" })),
    ];

    for (const item of allItems as Record<string, unknown>[]) {
      const textForEmbedding = `${item.role ?? item.title ?? ""} ${item.company ?? item.organizer ?? ""} ${Array.isArray(item.skills) ? item.skills.join(" ") : ""} ${item.description ?? ""}`;
      await upsertOpportunity({
        ID: String(item.id ?? item.slug ?? Math.random()),
        TYPE: String(item._type),
        TITLE: String(item.role ?? item.title ?? "Untitled"),
        COMPANY: item.company ? String(item.company) : item.organizer ? String(item.organizer) : undefined,
        DESCRIPTION: item.description ? String(item.description) : undefined,
        LOCATION: item.location ? String(item.location) : undefined,
        LOCATION_TYPE: item.locationType ? String(item.locationType) : undefined,
        SKILLS: Array.isArray(item.skills) ? JSON.stringify(item.skills) : undefined,
        SALARY_RANGE: item.salaryRange ? String(item.salaryRange) : item.stipend ? String(item.stipend) : undefined,
        DEADLINE: item.deadline ? String(item.deadline) : item.registrationDeadline ? String(item.registrationDeadline) : undefined,
        APPLY_URL: item.applyUrl ? String(item.applyUrl) : undefined,
        SOURCE: "scraper",
        EMBEDDING: embedText(textForEmbedding),
        IS_ACTIVE: 1,
      });
      synced++;
    }

    return NextResponse.json({ success: true, synced, total: allItems.length });
  } catch (error) {
    const msg = error instanceof Error ? error.message : "Sync failed";
    console.error("[/api/db2/sync]", msg);
    return NextResponse.json({ success: false, error: msg }, { status: 500 });
  }
}

/** GET /api/db2/sync — Check Db2 connection status */
export async function GET() {
  const { testConnection } = await import("@/services/db2/connection");
  const connected = await testConnection();
  return NextResponse.json({
    success: true,
    db2Connected: connected,
    configured: db2Config.isConfigured,
    message: connected
      ? "IBM Db2 is connected and ready."
      : db2Config.isConfigured
      ? "Db2 credentials found but connection failed. Check hostname/port."
      : "IBM Db2 not configured. Add DB2_* vars to .env.local.",
  });
}

