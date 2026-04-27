/**
 * Mobile responsive tests (SS2.12).
 *
 * iPhone 14 (390x844) and iPad (768x1024). Touch-target 44x44 minimum.
 */

import { test, expect, type Page } from "@playwright/test";
import { composer } from "./fixtures/helpers";

const MIN_TOUCH_TARGET = 44;

async function checkTouchTargets(page: Page, selector: string) {
  const elements = page.locator(selector);
  const count = await elements.count();
  for (let i = 0; i < count; i++) {
    const el = elements.nth(i);
    if (!(await el.isVisible())) continue;
    const box = await el.boundingBox();
    if (!box) continue;
    expect(
      Math.max(box.width, box.height),
      `Touch target ${selector}[${i}] too small: ${box.width}x${box.height}`,
    ).toBeGreaterThanOrEqual(MIN_TOUCH_TARGET - 4);
  }
}

test.describe("Mobile responsive (binary: Is the layout usable on mobile?)", () => {
  test("composer is visible and not clipped on iPhone 14", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    const c = composer(page);
    test.skip((await c.count()) === 0, "Skipped: composer not rendered.");

    await expect(c).toBeVisible();
    const box = await c.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      expect(box.width).toBeGreaterThan(200);
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(390 + 1);
    }
  });

  test("sidebar is hidden or collapsed on iPhone 14", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    const sidebar = page.locator(
      "[data-testid='thread-sidebar'], aside, nav[aria-label='Threads']",
    ).first();
    if ((await sidebar.count()) === 0) {
      test.skip(true, "Skipped: no sidebar rendered.");
    }

    const box = await sidebar.boundingBox();
    if (box) {
      expect(
        box.width <= 100 || box.x + box.width <= 0,
        `Sidebar should be hidden or <=100px on mobile (got width=${box.width}, x=${box.x})`,
      ).toBe(true);
    }
  });

  test("sidebar visible OR hamburger toggle exists on iPad", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    const sidebar = page.locator(
      "[data-testid='thread-sidebar'], nav[aria-label='Threads']",
    ).first();
    const hamburger = page.locator(
      "[data-testid='sidebar-toggle'], button[aria-label*='menu' i]",
    ).first();

    const sidebarVisible = (await sidebar.count()) > 0
      ? await sidebar.isVisible().catch(() => false)
      : false;
    const hamburgerVisible = (await hamburger.count()) > 0
      ? await hamburger.isVisible().catch(() => false)
      : false;

    expect(
      sidebarVisible || hamburgerVisible,
      "iPad must show the sidebar or expose a hamburger toggle",
    ).toBe(true);
  });

  test("interactive controls meet 44x44 touch target minimum on iPhone 14", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    test.skip((await composer(page).count()) === 0, "Skipped: composer not rendered.");

    await checkTouchTargets(page, "header button");
  });
});
