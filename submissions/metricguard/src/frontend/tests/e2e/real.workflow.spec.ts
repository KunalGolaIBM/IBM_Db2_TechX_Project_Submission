/**
 * REAL-BACKEND tests. No HTTP is stubbed: the browser talks to FastAPI on :8000, which runs
 * the pipeline against IBM Db2 and writes audit rows. Requires `make api` and Db2 up.
 */
import { expect, test, type Page } from "@playwright/test";

const API = process.env.API_BASE_URL ?? "http://localhost:8000";

let MODE: "LLM" | "DEMO_RULE_BASED";

test.beforeAll(async ({ request }) => {
  const res = await request.get(`${API}/api/health`).catch(() => null);
  if (!res || !res.ok()) throw new Error(`Real backend not healthy at ${API}/api/health. Start Db2 and \`make api\` first.`);
  MODE = (await res.json()).planner.execution_mode;
});

async function runDemo(page: Page, id: string) {
  await page.getByTestId(`demo-${id}`).click();
  // a real model can take tens of seconds; the product shows a loading state meanwhile
  await expect(page.getByTestId("analysis-view")).toBeVisible({ timeout: 120_000 });
}

test("header reflects the real health response", async ({ page, request }) => {
  const health = await (await request.get(`${API}/api/health`)).json();
  await page.goto("/");
  const badge = page.getByTestId("db2-status");
  await expect(badge).toHaveAttribute("data-tone", "ok");
  await expect(badge).toContainText("connected");
  await expect(badge).toContainText(health.database.service_level.replace("DB2 ", "Db2 "));
  if (MODE === "DEMO_RULE_BASED") {
    await expect(page.getByTestId("header-mode")).toHaveText(/Demo planner/);
    await expect(page.getByTestId("pre-question-demo-note")).toBeVisible();
  } else {
    await expect(page.getByTestId("header-mode")).toContainText(health.planner.model);
    await expect(page.getByTestId("header-mode")).not.toContainText(/Demo/);
    await expect(page.getByTestId("pre-question-llm-note")).toBeVisible();
    await expect(page.getByTestId("pre-question-demo-note")).toHaveCount(0);
  }
});

test("scenario 1: verified net revenue, number equals the API, evidence is inspectable", async ({ page, request }) => {
  await page.goto("/");
  await runDemo(page, "trusted");

  const apiRes = await (await request.post(`${API}/api/analyze`, { data: { question: "What was our net revenue in June 2026?" }, timeout: 90_000 })).json();
  expect(apiRes.status).toBe("VERIFIED");

  await expect(page.getByTestId("status-badge").first()).toHaveAttribute("data-status", "VERIFIED");
  await expect(page.getByTestId("headline-value")).toHaveText(apiRes.answer.headline.formatted);
  await expect(page.getByTestId("headline-value")).toHaveText(/^\$[\d,]+\.\d{2}$/);

  // demo disclosure is visible without opening anything
  const disclosure = page.getByTestId("mode-disclosure");
  await expect(disclosure).toBeVisible();
  await expect(disclosure).toHaveAttribute("data-mode", MODE);
  if (MODE === "DEMO_RULE_BASED") {
    await expect(disclosure).toContainText(apiRes.planner.disclosure);
    await expect(disclosure).toContainText(/not an LLM/i);
  } else {
    await expect(disclosure).toContainText(apiRes.planner.model);
    await expect(disclosure).not.toContainText(/Demo/);
  }

  // evidence panel
  await expect(page.getByTestId("verdict-status")).toHaveText("Verified");
  await expect(page.getByTestId("checks-list").locator("li")).toHaveCount(11);
  await expect(page.getByTestId("sql-text")).toContainText("METRICGUARD.ORDERS");
  await expect(page.getByTestId("sec-metrics")).toContainText("net_revenue@1.0.0");
  await expect(page.getByTestId("sec-metrics")).toContainText("Matches Db2 registry");

  // copy SQL puts the exact statement on the clipboard
  const sqlOnScreen = await page.getByTestId("sql-text").innerText();
  await page.getByTestId("copy-sql").click();
  await expect(page.getByTestId("copy-sql")).toContainText("Copied");
  const clip = await page.evaluate(() => navigator.clipboard.readText());
  expect(clip).toContain("WITH eligible_orders");
  expect(clip.replace(/\s+/g, " ")).toContain(sqlOnScreen.replace(/^\s*\d+\s*/gm, "").replace(/\s+/g, " ").slice(0, 60));

  // parameters section
  await page.getByRole("button", { name: /Query parameters/ }).click();
  await expect(page.getByTestId("params-table")).toContainText("date_start_inclusive");
});

test("grouped question draws a chart from backend series and offers a table view", async ({ page }) => {
  await page.goto("/");
  await runDemo(page, "precise");
  await expect(page.getByTestId("chart")).toBeVisible();
  await expect(page.getByTestId("chart")).toHaveAttribute("data-chart-type", "bar");
  await page.getByTestId("view-table").click();
  const rows = page.getByTestId("result-table").locator("tbody tr");
  await expect(rows).toHaveCount(4);
  await expect(page.getByTestId("result-table")).toContainText("EMEA");
});

test("scenario 2: ranked question headlines the top region; ambiguous question offers verbatim clarifications", async ({ page }) => {
  await page.goto("/");
  // Replaces "Show our best-performing region." (a real model answers it AMBIGUOUS or BLOCKED, see
  // docs/AI_PROVIDER_CONFIGURATION.md). Both planners group by region, sort desc, limit 1; the seed data is deterministic.
  await runDemo(page, "ranked");
  await expect(page.getByTestId("analysis-view")).toHaveAttribute("data-status", "VERIFIED");
  await expect(page.getByTestId("analysis-view")).toContainText("Top region: NA · Net Revenue (Q2 2026)");
  await expect(page.getByTestId("headline-value")).toHaveText("$138,679.66");
  await expect(page.getByTestId("answer-summary")).toHaveText("The top region by Net Revenue for Q2 2026 is NA ($138,679.66).");

  await runDemo(page, "ambiguous");
  await expect(page.getByTestId("analysis-view")).toHaveAttribute("data-status", "AMBIGUOUS");
  await expect(page.getByTestId("ambiguous-panel")).toBeVisible();
  await expect(page.getByTestId("headline-value")).toHaveCount(0);

  // choosing an option re-submits its suggested question and returns a verified, real answer
  await page.getByTestId("clarify-net_revenue").click();
  await expect(page.getByTestId("analysis-view")).toHaveAttribute("data-status", "VERIFIED");
  await expect(page.getByTestId("echo-question")).toContainText("net revenue in Q2 2026");
  await expect(page.getByTestId("headline-value")).toHaveText(/^\$[\d,]+\.\d{2}$/);

  // a more precise question that the API supports
  await runDemo(page, "precise");
  await expect(page.getByTestId("analysis-view")).toHaveAttribute("data-status", "VERIFIED");
});

test("scenario 3: unsafe instruction is blocked, nothing executes, and the audit trail records it", async ({ page, request }) => {
  await page.goto("/");
  await runDemo(page, "unsafe");
  await expect(page.getByTestId("analysis-view")).toHaveAttribute("data-status", "BLOCKED");
  await expect(page.getByTestId("blocked-no-sql")).toContainText("No SQL was executed");
  await expect(page.getByTestId("blocked-reasons")).toContainText("WRITE_INTENT");
  await expect(page.getByTestId("sql-block")).toHaveCount(0);
  await expect(page.getByTestId("result-table")).toHaveCount(0);

  const requestId = (await page.getByTestId("request-id").innerText()).trim();
  // audit trail: follow the link, and confirm the row exists in Db2 through the API
  await page.getByTestId("audit-link").click();
  await expect(page).toHaveURL(new RegExp(`/audit/${requestId}$`));
  await expect(page.getByTestId("audit-detail")).toHaveAttribute("data-status", "BLOCKED");
  await expect(page.getByTestId("audit-question")).toContainText("delete every order");
  await expect(page.getByTestId("request-id")).toHaveText(requestId);
  const stored = await (await request.get(`${API}/api/audit/${requestId}`)).json();
  expect(stored.status).toBe("BLOCKED");
  expect(stored.sql).toBeNull();
});

test("audit history lists real Db2 records and opens a detail view", async ({ page, request }) => {
  const list = await (await request.get(`${API}/api/audit?limit=15`)).json();
  expect(list.total).toBeGreaterThan(0);

  await page.goto("/audit");
  await expect(page.getByTestId("audit-table")).toBeVisible();
  await expect(page.getByTestId("audit-row")).toHaveCount(Math.min(15, list.total));
  await expect(page.getByTestId("audit-range")).toContainText(`of ${list.total}`);
  await expect(page.getByTestId("audit-row").first()).toContainText(list.items[0].question);

  // status filter goes through the API
  await page.getByTestId("status-filter").selectOption("BLOCKED");
  const statuses = () => page.getByTestId("audit-row").getByTestId("status-badge").evaluateAll((els) => [...new Set(els.map((e) => e.getAttribute("data-status")))]);
  await expect.poll(statuses).toEqual(["BLOCKED"]);

  // detail of a verified record shows stored SQL and result preview
  await page.getByTestId("status-filter").selectOption("VERIFIED");
  await expect.poll(statuses).toEqual(["VERIFIED"]);
  await page.getByTestId("audit-row").first().getByRole("link").click();
  await expect(page.getByTestId("audit-detail")).toHaveAttribute("data-status", "VERIFIED");
  await expect(page.getByTestId("sql-text")).toContainText("SELECT");
  await expect(page.getByTestId("checks-list").locator("li")).toHaveCount(11);
  // the stored record's mode must match what the API says it is (older rows may be demo, newer ones LLM)
  const id = page.url().split("/").pop()!;
  const stored = await (await request.get(`${API}/api/audit/${id}`)).json();
  await expect(page.getByTestId("mode-disclosure")).toHaveAttribute("data-mode", stored.execution_mode);
});

test("unknown audit id shows a not-found error from the real backend", async ({ page }) => {
  await page.goto("/audit/00000000-0000-4000-8000-000000000000");
  await expect(page.getByTestId("audit-detail-error")).toHaveAttribute("data-kind", "not_found");
});

test("example list comes from GET /api/examples", async ({ page, request }) => {
  const ex = await (await request.get(`${API}/api/examples`)).json();
  await page.goto("/");
  await page.getByRole("button", { name: /Show all API examples/ }).click();
  await expect(page.locator("#all-examples li")).toHaveCount(ex.examples.length);
});
