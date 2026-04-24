/**
 * Accessibility tests (SS2.13).
 *
 * Uses `@axe-core/playwright` to enforce WCAG 2.2 AA. Zero serious or
 * critical violations required.
 *
 * Pairs with the static checker at `frontend/scripts/check_axe_a11y.ts`
 * and the ESLint plugin `eslint-plugin-jsx-a11y`.
 */

import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { composer } from "./fixtures/helpers";

test.describe("Accessibility (binary: Are there serious or critical a11y violations?)", () => {
  test("home page has zero serious or critical axe violations", async ({ page }) => {
    await page.goto("/");

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag22aa", "best-practice"])
      .analyze();

    const blockers = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    );

    expect(
      blockers,
      `Found ${blockers.length} serious/critical a11y violations: ` +
        blockers.map((v) => `${v.id} (${v.nodes.length} nodes)`).join(", "),
    ).toEqual([]);
  });

  test("tab order reaches the composer", async ({ page }) => {
    await page.goto("/");
    const c = composer(page);
    test.skip((await c.count()) === 0, "Skipped: composer not rendered.");

    let reached = false;
    for (let i = 0; i < 25; i++) {
      await page.keyboard.press("Tab");
      const focused = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (!el) return { tag: "", testid: "", ariaLabel: "" };
        return {
          tag: el.tagName,
          testid: el.getAttribute("data-testid") ?? "",
          ariaLabel: el.getAttribute("aria-label") ?? "",
        };
      });
      if (
        focused.tag === "TEXTAREA"
        || focused.testid === "composer"
        || /compose/i.test(focused.ariaLabel)
      ) {
        reached = true;
        break;
      }
    }
    expect(reached, "Composer must be reachable via Tab").toBe(true);
  });
});
