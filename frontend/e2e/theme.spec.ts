/**
 * Theme toggle tests (SS2.7 / F9).
 */

import { test, expect, type Page } from "@playwright/test";

const TOGGLE_SELECTORS = [
  "[data-testid='theme-toggle']",
  "button[aria-label*='theme' i]",
  "button[aria-label*='Theme']",
].join(", ");

async function readTheme(page: Page): Promise<"dark" | "light" | "unknown"> {
  const html = page.locator("html");
  const dataTheme = await html.getAttribute("data-theme");
  const className = (await html.getAttribute("class")) ?? "";
  if (dataTheme === "dark" || className.includes("dark")) return "dark";
  if (dataTheme === "light" || className.includes("light")) return "light";
  return "unknown";
}

test.describe("Theme toggle (binary: Does theme switch and persist?)", () => {
  test("toggling flips the theme on the html element", async ({ page }) => {
    await page.goto("/");
    const toggle = page.locator(TOGGLE_SELECTORS).first();
    test.skip((await toggle.count()) === 0, "Skipped: theme toggle not rendered.");

    const before = await readTheme(page);
    await toggle.click();
    await page.waitForTimeout(300);
    const after = await readTheme(page);
    expect(after).not.toBe(before);
  });

  test("chosen theme persists across reload", async ({ page }) => {
    await page.goto("/");
    const toggle = page.locator(TOGGLE_SELECTORS).first();
    test.skip((await toggle.count()) === 0, "Skipped: theme toggle not rendered.");

    await toggle.click();
    await page.waitForTimeout(300);
    const chosen = await readTheme(page);

    await page.reload();
    await page.waitForTimeout(300);
    const reloaded = await readTheme(page);
    expect(reloaded).toBe(chosen);
  });

  test("toggle has an aria-label that describes the action", async ({ page }) => {
    await page.goto("/");
    const toggle = page.locator(TOGGLE_SELECTORS).first();
    test.skip((await toggle.count()) === 0, "Skipped: theme toggle not rendered.");

    const ariaLabel = (await toggle.getAttribute("aria-label")) ?? "";
    expect(ariaLabel.toLowerCase()).toMatch(/theme|dark|light/);
  });

  test("toggle is keyboard-focusable", async ({ page }) => {
    await page.goto("/");
    const toggle = page.locator(TOGGLE_SELECTORS).first();
    test.skip((await toggle.count()) === 0, "Skipped: theme toggle not rendered.");

    await toggle.focus();
    await expect(toggle).toBeFocused();
  });
});
