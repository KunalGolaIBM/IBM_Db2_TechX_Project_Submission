/**
 * REAL META INFERENCE tests. Skipped (with the reason shown) unless the live backend reports
 * provider "meta". Each question triggers a real Muse Spark request through LangChain, then the
 * deterministic pipeline on real Db2. Keep this file small: it costs API credits.
 */
import { expect, test } from "@playwright/test";

const API = process.env.API_BASE_URL ?? "http://localhost:8000";
let health: { planner: { provider: string | null; model: string | null; execution_mode: string | null } };

test.beforeAll(async ({ request }) => {
  const res = await request.get(`${API}/api/health`);
  health = await res.json();
});

test.beforeEach(() => {
  test.skip(health.planner.provider !== "meta", `backend planner provider is ${health.planner.provider}, not meta`);
});
test.setTimeout(120_000);

test("a genuinely model-planned grouped question: ranking by region, real numbers, truthful provider label", async ({ page, request }) => {
  const q = "Which region had the highest net revenue in Q2 2026?";
  await page.goto("/");
  await page.getByLabel(/Ask a question/).fill(q);
  await page.getByTestId("submit-question").click();
  await expect(page.getByTestId("analysis-view")).toBeVisible({ timeout: 90_000 });

  await expect(page.getByTestId("analysis-view")).toHaveAttribute("data-status", "VERIFIED");
  const disclosure = page.getByTestId("mode-disclosure");
  await expect(disclosure).toHaveAttribute("data-mode", "LLM");
  await expect(page.getByTestId("llm-label")).toHaveText(`AI planner · Meta Model API · ${health.planner.model}`);
  await expect(disclosure).not.toContainText(/Demo|rule-based/);

  // the plan groups by region (the demo planner could not do this) and the answer names a region
  await page.getByRole("button", { name: /How the question was read/ }).click();
  await expect(page.getByTestId("interpretation")).toContainText("region");
  await expect(page.getByTestId("answer-summary")).toContainText(/NA|EMEA|APAC|LATAM/);
  await expect(page.getByTestId("evidence-panel")).toContainText("langchain-meta");
  await expect(page.getByTestId("checks-list").locator("li")).toHaveCount(11);

  // audit trail records a real LLM execution
  const id = (await page.getByTestId("request-id").innerText()).trim();
  const stored = await (await request.get(`${API}/api/audit/${id}`)).json();
  expect(stored.execution_mode).toBe("LLM");
  expect(stored.planner).toBe("langchain-meta");
  expect(stored.planner_model).toBe(health.planner.model);
  await page.getByTestId("audit-link").click();
  await expect(page.getByTestId("mode-disclosure")).toHaveAttribute("data-mode", "LLM");
  await expect(page.getByTestId("llm-label")).toContainText("Meta Model API");
});

test("an unsafe instruction is blocked with a real model in the loop and no SQL runs", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("demo-unsafe").click();
  await expect(page.getByTestId("analysis-view")).toBeVisible({ timeout: 90_000 });
  await expect(page.getByTestId("analysis-view")).toHaveAttribute("data-status", "BLOCKED");
  await expect(page.getByTestId("blocked-no-sql")).toContainText("No SQL was executed");
  await expect(page.getByTestId("sql-block")).toHaveCount(0);
  await expect(page.getByTestId("mode-disclosure")).toHaveAttribute("data-mode", "LLM");
});

test("audit history labels Meta-planned rows", async ({ page }) => {
  await page.goto("/audit");
  await expect(page.getByTestId("audit-table")).toBeVisible();
  await expect(page.getByTestId("audit-table")).toContainText("AI planner · Meta");
});
