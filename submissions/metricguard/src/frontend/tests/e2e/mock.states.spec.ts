/**
 * MOCKED-RESPONSE tests. Only the endpoints named in each test are stubbed (with recorded real
 * responses from docs/examples, or hand-built error bodies); every other /api call still hits the
 * real backend. These cover states the live system cannot be made to produce on demand.
 * They do NOT prove backend behavior.
 */
import { expect, test, type Page, type Route } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const API = "http://localhost:8000";
const rec = (name: string) => JSON.parse(fs.readFileSync(path.resolve(__dirname, "../../../docs/examples", name), "utf8"));
const CORS = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "GET,POST,OPTIONS" };

type Stub = { status?: number; body?: unknown; delayMs?: number; abort?: boolean };

/** Stub specific "METHOD /path" keys; pass everything else through to the real backend. */
async function stub(page: Page, stubs: Record<string, Stub>, opts: { abortAll?: boolean } = {}) {
  const calls: Record<string, number> = {};
  await page.route(`${API}/api/**`, async (route: Route) => {
    const req = route.request();
    const url = new URL(req.url());
    if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
    const key = `${req.method()} ${url.pathname}`;
    calls[key] = (calls[key] ?? 0) + 1;
    if (opts.abortAll) return route.abort("connectionrefused");
    const s = stubs[key];
    if (!s) return route.continue();
    if (s.delayMs) await new Promise((r) => setTimeout(r, s.delayMs));
    if (s.abort) return route.abort("connectionrefused");
    return route.fulfill({ status: s.status ?? 200, headers: { ...CORS, "content-type": "application/json" }, body: JSON.stringify(s.body) });
  });
  return calls;
}

const ask = async (page: Page, q: string) => {
  await page.getByLabel(/Ask a question/).fill(q);
  await page.getByTestId("submit-question").click();
};

test("backend unavailable: header says API offline and asking shows a retryable network error", async ({ page }) => {
  await stub(page, {}, { abortAll: true });
  await page.goto("/");
  await expect(page.getByTestId("db2-status")).toHaveAttribute("data-tone", "bad");
  await expect(page.getByTestId("db2-status")).toContainText("API offline");
  await expect(page.getByTestId("db2-status")).not.toContainText("connected");
  await ask(page, "What was our net revenue in June 2026?");
  await expect(page.getByTestId("transport-error")).toHaveAttribute("data-kind", "network");
  await expect(page.getByTestId("retry-transport")).toBeVisible();
});

test("Db2 disconnected: health 503 is shown as 'Db2 unreachable', never 'connected'", async ({ page }) => {
  const h = rec("health.json");
  h.status = "degraded"; h.database = { ...h.database, status: "down", latency_ms: null, error: { code: "DATABASE_UNAVAILABLE", message: "IBM Db2 is unavailable.", details: [], sqlstate: "08001" } };
  await stub(page, { "GET /api/health": { status: 503, body: h } });
  await page.goto("/");
  await expect(page.getByTestId("db2-status")).toContainText("Db2 unreachable");
  await expect(page.getByTestId("db2-status")).not.toContainText("connected");
});

test("503 PLANNER_UNAVAILABLE: shows 'AI planner unavailable' and does not fall back to demo results", async ({ page }) => {
  await stub(page, { "POST /api/analyze": { status: 503, body: { request_id: null, error: { code: "PLANNER_UNAVAILABLE", message: "No Anthropic API key is configured.", details: [], sqlstate: null } } } });
  await page.goto("/");
  await ask(page, "What was our net revenue in June 2026?");
  const err = page.getByTestId("transport-error");
  await expect(err).toHaveAttribute("data-kind", "planner_unavailable");
  await expect(err).toContainText("AI planner unavailable");
  await expect(page.getByTestId("analysis-view")).toHaveCount(0);
  await expect(page.getByTestId("headline-value")).toHaveCount(0);
});

test("EXECUTION_FAILED (recorded response): error + SQLSTATE + retry, no numbers, not verified", async ({ page }) => {
  const failed = rec("analysis-failure.json");
  const calls = await stub(page, { "POST /api/analyze": { body: failed } });
  await page.goto("/");
  await ask(page, failed.question);
  await expect(page.getByTestId("analysis-view")).toHaveAttribute("data-status", "EXECUTION_FAILED");
  await expect(page.getByTestId("failed-error")).toContainText("08001");
  await expect(page.getByTestId("headline-value")).toHaveCount(0);
  await expect(page.getByTestId("verdict-status")).toHaveText("Execution failed");
  await page.getByTestId("retry").click();
  await expect.poll(() => calls["POST /api/analyze"]).toBe(2);
});

test("EXECUTED_WITH_WARNINGS (recorded response): numbers plus a visible warning banner", async ({ page }) => {
  const w = rec("executed-with-warnings.json");
  await stub(page, { "POST /api/analyze": { body: w } });
  await page.goto("/");
  await ask(page, w.question);
  await expect(page.getByTestId("analysis-view")).toHaveAttribute("data-status", "EXECUTED_WITH_WARNINGS");
  await expect(page.getByTestId("warning-banner")).toContainText("no data");
  await expect(page.getByTestId("headline-value")).toHaveText(w.answer.headline.formatted);
});

test("LLM mode (synthetic Meta response): shows provider and model, not the demo label", async ({ page }) => {
  const r = rec("successful-analysis.json");
  r.planner = { name: "langchain-meta", provider: "meta", model: "muse-spark-1.3", execution_mode: "LLM", disclosure: null };
  await stub(page, { "POST /api/analyze": { body: r } });
  await page.goto("/");
  await ask(page, r.question);
  const d = page.getByTestId("mode-disclosure");
  await expect(d).toHaveAttribute("data-mode", "LLM");
  await expect(page.getByTestId("llm-label")).toHaveText("AI planner · Meta Model API · muse-spark-1.3");
  await expect(d).not.toContainText("Demo Planner");
});

test("malformed 200 response is discarded, not rendered", async ({ page }) => {
  await stub(page, { "POST /api/analyze": { body: { status: "VERIFIED", answer: "trust me" } } });
  await page.goto("/");
  await ask(page, "What was our net revenue in June 2026?");
  await expect(page.getByTestId("transport-error")).toHaveAttribute("data-kind", "malformed");
  await expect(page.getByTestId("headline-value")).toHaveCount(0);
});

test("slow request: loading state with hint, and a second click cannot start a duplicate request", async ({ page }) => {
  const calls = await stub(page, { "POST /api/analyze": { body: rec("successful-analysis.json"), delayMs: 6000 } });
  await page.goto("/");
  await page.getByLabel(/Ask a question/).fill("What was our net revenue in June 2026?");
  await page.getByTestId("submit-question").click();
  await expect(page.getByTestId("loading-state")).toBeVisible();
  await expect(page.getByTestId("submit-question")).toHaveCount(0); // replaced by Cancel while loading
  await page.keyboard.press("Control+Enter");
  await page.getByTestId("demo-trusted").click({ force: true }).catch(() => {});
  await expect(page.getByTestId("slow-hint")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("analysis-view")).toBeVisible({ timeout: 15_000 });
  expect(calls["POST /api/analyze"]).toBe(1);
});

test("empty result: warning instead of an empty chart", async ({ page }) => {
  const r = rec("grouped-analysis.json");
  r.result = { ...r.result, rows: [], row_count: 0 };
  r.chart = { ...r.chart, series: r.chart.series.map((s: { points: unknown[] }) => ({ ...s, points: [] })) };
  await stub(page, { "POST /api/analyze": { body: r } });
  await page.goto("/");
  await ask(page, r.question);
  await expect(page.getByText("No rows returned").first()).toBeVisible();
  await expect(page.getByTestId("chart")).toHaveCount(0);
});

test("audit history retrieval failure shows an error with retry; then recovers", async ({ page }) => {
  let fail = true;
  await page.route(`${API}/api/audit?**`, async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
    if (fail) return route.fulfill({ status: 500, headers: { ...CORS, "content-type": "application/json" }, body: JSON.stringify({ request_id: null, error: { code: "INTERNAL_ERROR", message: "boom", details: [], sqlstate: null } }) });
    return route.continue();
  });
  await page.goto("/audit");
  await expect(page.getByTestId("audit-error")).toBeVisible();
  fail = false;
  await page.getByTestId("retry-transport").click();
  await expect(page.getByTestId("audit-table")).toBeVisible();
});

test("empty audit history shows an empty state", async ({ page }) => {
  await stub(page, { "GET /api/audit": { body: { items: [], total: 0, limit: 15, offset: 0 } } });
  await page.goto("/audit");
  await expect(page.getByTestId("audit-empty")).toBeVisible();
});
