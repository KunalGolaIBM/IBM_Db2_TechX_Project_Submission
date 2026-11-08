/** REAL-BACKEND, mobile viewport: layout must not overflow horizontally. */
import { expect, test } from "@playwright/test";

test("no horizontal overflow on a verified result with a long SQL statement", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("demo-precise").click();
  await expect(page.getByTestId("analysis-view")).toBeVisible();
  await expect(page.getByTestId("sql-text")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  // SQL scrolls inside its own box
  const scrollable = await page.getByTestId("sql-block").locator("pre").evaluate((el) => el.scrollWidth > el.clientWidth);
  expect(scrollable).toBe(true);
});

test("audit list uses cards on mobile and does not overflow", async ({ page }) => {
  await page.goto("/audit");
  await expect(page.getByTestId("audit-cards")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
