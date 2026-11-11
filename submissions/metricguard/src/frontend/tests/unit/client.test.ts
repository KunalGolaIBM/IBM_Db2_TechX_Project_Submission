import { afterEach, describe, expect, it, vi } from "vitest";
import { analyze, ApiError, assertAnalyzeResponse, getHealth } from "@/lib/api/client";
import { FIX } from "./fixtures";

const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }));
afterEach(() => vi.restoreAllMocks());

describe("assertAnalyzeResponse", () => {
  it.each(Object.entries({ verified: FIX.verified, ambiguous: FIX.ambiguous, blocked: FIX.blocked, failed: FIX.failed, warnings: FIX.warnings }))("accepts recorded %s", (_n, r) => {
    expect(assertAnalyzeResponse(r)).toBe(r);
  });
  it("rejects unknown statuses", () => expect(() => assertAnalyzeResponse({ ...FIX.verified, status: "PROBABLY_FINE" })).toThrow(/unknown status/));
  it("rejects executed status without a result", () => expect(() => assertAnalyzeResponse({ ...FIX.verified, result: null })).toThrow(ApiError));
  it("rejects missing planner metadata", () => expect(() => assertAnalyzeResponse({ ...FIX.verified, planner: undefined })).toThrow(/planner/));
  it("rejects non-objects", () => expect(() => assertAnalyzeResponse("nope")).toThrow(ApiError));
});

describe("analyze()", () => {
  it("maps 503 PLANNER_UNAVAILABLE to its own kind", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json({ request_id: null, error: { code: "PLANNER_UNAVAILABLE", message: "No key", details: [], sqlstate: null } }, 503)));
    await expect(analyze("hello there")).rejects.toMatchObject({ kind: "planner_unavailable", status: 503 });
  });
  it("maps 422 with details", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json({ error: { code: "INVALID_REQUEST", message: "bad", details: [{ field: "question", issue: "too short" }] } }, 422)));
    await expect(analyze("hi")).rejects.toMatchObject({ kind: "invalid_request", details: ["question: too short"] });
  });
  it("maps fetch failure to network", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    await expect(analyze("hello there")).rejects.toMatchObject({ kind: "network" });
  });
  it("flags a 200 with a malformed body", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json({ hello: "world" })));
    await expect(analyze("hello there")).rejects.toMatchObject({ kind: "malformed" });
  });
  it("returns a valid response untouched", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json(FIX.verified)));
    await expect(analyze("hello there")).resolves.toMatchObject({ status: "VERIFIED" });
  });
});

describe("getHealth()", () => {
  it("returns the body of a 503 health response (Db2 down) instead of throwing", async () => {
    const down = { ...FIX.health, status: "degraded", database: { ...FIX.health.database, status: "down" } };
    vi.stubGlobal("fetch", vi.fn(() => json(down, 503)));
    await expect(getHealth()).resolves.toMatchObject({ database: { status: "down" } });
  });
});
