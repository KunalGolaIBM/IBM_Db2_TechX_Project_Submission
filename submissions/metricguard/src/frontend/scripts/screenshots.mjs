// Captures QA screenshots from the REAL running app + backend. Usage: node scripts/screenshots.mjs [outDir]
import { chromium } from "@playwright/test";
import path from "node:path";

const out = path.resolve(process.argv[2] ?? "../docs/screenshots");
const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const browser = await chromium.launch();

async function run(name, viewport, steps) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.log(`[${name}] pageerror:`, e.message));
  page.on("console", (m) => { if (m.type() === "error") console.log(`[${name}] console.error:`, m.text()); });
  await steps(page, (n, opts = {}) => page.screenshot({ path: path.join(out, `${name}-${n}.png`), ...opts }));
  await ctx.close();
}

const ask = async (page, testid) => {
  await page.getByTestId(testid).click();
  await page.getByTestId("analysis-view").waitFor({ timeout: 120000 });
  await page.waitForTimeout(400);
};

await run("desktop", { width: 1440, height: 900 }, async (page, shot) => {
  await page.goto(BASE);
  await page.getByTestId("db2-status").waitFor();
  await page.waitForTimeout(1200);
  await shot("01-home");
  await ask(page, "demo-trusted");
  await shot("02-verified", { fullPage: true });
  await ask(page, "demo-ranked");
  await shot("03-top-region", { fullPage: true });
  await ask(page, "demo-ambiguous");
  await shot("04-ambiguous", { fullPage: true });
  await ask(page, "demo-unsafe");
  await shot("05-blocked-unsafe", { fullPage: true });
  await ask(page, "demo-precise");
  await shot("06-by-region-chart", { fullPage: true });
  await page.goto(`${BASE}/audit`);
  await page.getByTestId("audit-table").waitFor();
  await shot("07-audit-list", { fullPage: true });
  await page.getByTestId("audit-row").first().getByRole("link").click();
  await page.getByTestId("audit-detail").waitFor();
  await page.waitForTimeout(400);
  await shot("08-audit-detail", { fullPage: true });
});

await run("mobile", { width: 390, height: 844 }, async (page, shot) => {
  await page.goto(BASE);
  await page.getByTestId("db2-status").waitFor();
  await page.waitForTimeout(1000);
  await shot("01-home");
  await ask(page, "demo-trusted");
  await shot("02-verified", { fullPage: true });
  await ask(page, "demo-precise");
  await shot("03-chart", { fullPage: true });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  console.log("[mobile] horizontal overflow px:", overflow);
  await page.goto(`${BASE}/audit`);
  await page.getByTestId("audit-cards").waitFor();
  await shot("04-audit", { fullPage: true });
});

await run("tablet", { width: 820, height: 1100 }, async (page, shot) => {
  await page.goto(BASE);
  await page.getByTestId("db2-status").waitFor();
  await ask(page, "demo-precise");
  await shot("01-chart", { fullPage: true });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  console.log("[tablet] horizontal overflow px:", overflow);
});

// ---- MOCKED states (stubbed HTTP, recorded real responses). File names are prefixed "mock-". ----
import fs from "node:fs";
const rec = (n) => JSON.parse(fs.readFileSync(path.resolve("../docs/examples", n), "utf8"));
const CORS = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "GET,POST,OPTIONS" };
async function mockRun(name, stubAnalyze, abortAll = false) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.route("http://localhost:8000/api/**", async (route) => {
    const req = route.request();
    if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
    if (abortAll) return route.abort("connectionrefused");
    if (req.method() === "POST" && req.url().endsWith("/api/analyze")) return route.fulfill({ status: 200, headers: { ...CORS, "content-type": "application/json" }, body: JSON.stringify(stubAnalyze) });
    return route.continue();
  });
  await page.goto(BASE);
  await page.waitForTimeout(1000);
  await page.getByLabel(/Ask a question/).fill("mocked question");
  await page.getByTestId("submit-question").click();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: path.join(out, `mock-${name}.png`), fullPage: true });
  await ctx.close();
}
await mockRun("execution-failed", rec("analysis-failure.json"));
await mockRun("executed-with-warnings", rec("executed-with-warnings.json"));
await mockRun("api-offline", null, true);

await browser.close();
