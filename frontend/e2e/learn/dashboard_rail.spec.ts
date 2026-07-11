/**
 * C1 Dashboard rail + greeting (FR-1/2/5/6/7/8 + C1-fix FR-1/2/8/13).
 *
 * T1: browser-seeded InMemoryEngineDb via `__PREACT_E2E_SEED__`.
 * Rail fail-once: `NEXT_PUBLIC_PREACT_E2E_HOOKS=1` (playwright webServer) +
 * `?e2e_rail_fail=1` opt-in on the retry rows (composition-root decorator).
 */

import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  LEARN_SEED_CORPUS,
  LEARN_SEED_GLOBAL_KEY,
  LEARN_LEARNER_ID,
} from "../fixtures/preact_learn_corpus";
import type { QuizSession } from "../../lib/wire/engine_entities";

function closedSession(
  id: string,
  endedAtLocal: Date,
): QuizSession {
  return {
    id,
    subject: "act-english",
    learner_id: LEARN_LEARNER_ID,
    mode: "adaptive",
    skill_focus: null,
    started_at: new Date(endedAtLocal.getTime() - 3_600_000).toISOString(),
    ended_at: endedAtLocal.toISOString(),
    score_correct: 5,
    score_total: 10,
    target_count: 30,
  };
}

async function seedBrowser(
  page: Page,
  sessions: readonly QuizSession[] = [],
): Promise<void> {
  const corpus = { ...LEARN_SEED_CORPUS, sessions };
  await page.addInitScript(
    ([key, body]) => {
      (window as unknown as Record<string, unknown>)[key as string] = body;
    },
    [LEARN_SEED_GLOBAL_KEY, corpus] as const,
  );
}

/** FR-13: axe wcag2a/aa on the loaded dashboard. */
async function expectNoAxeViolations(page: Page): Promise<void> {
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(axe.violations).toEqual([]);
}

test.describe("C1 dashboard rail + greeting", () => {
  test("cold_start_renders_honest_empty_state", async ({ page }) => {
    await seedBrowser(page, []);
    await page.goto("/learn");
    await expect(page.getByTestId("dashboard-root")).toBeVisible({
      timeout: 15_000,
    });
    await expectNoAxeViolations(page);
    await expect(page.getByTestId("streak-tile")).toContainText("Start a streak");
    await expect(page.getByTestId("weekly-tile")).toContainText("0 / 3 sessions");
    await expect(page.getByTestId("dashboard-greeting")).toContainText("Maya");
  });

  test("returning_learner_shows_streak_and_weekly", async ({ page }) => {
    const now = new Date(2026, 6, 10, 15, 0, 0, 0); // Fri Jul 10 2026 15:00 local
    await page.clock.install({ time: now });
    const sessions = [
      closedSession("d0", new Date(2026, 6, 10, 10, 0, 0, 0)),
      closedSession("d1", new Date(2026, 6, 9, 10, 0, 0, 0)),
      closedSession("d2", new Date(2026, 6, 8, 10, 0, 0, 0)),
    ];
    await seedBrowser(page, sessions);
    await page.goto("/learn");
    await expect(page.getByTestId("streak-tile")).toContainText("3-day streak", {
      timeout: 15_000,
    });
    await expectNoAxeViolations(page);
    await expect(page.getByTestId("weekly-tile")).toContainText("3 / 3 sessions");
  });

  test("injected_clock_midnight_determinism", async ({ page }) => {
    const justBeforeMidnight = new Date(2026, 6, 10, 23, 59, 59, 0);
    await page.clock.install({ time: justBeforeMidnight });
    const sessions = [
      closedSession("today", new Date(2026, 6, 10, 12, 0, 0, 0)),
    ];
    await seedBrowser(page, sessions);
    await page.goto("/learn");
    await expect(page.getByTestId("streak-tile")).toContainText("1-day streak", {
      timeout: 15_000,
    });
    await expectNoAxeViolations(page);
    await page.clock.fastForward("00:00:02"); // → 00:00:01 next day
    await page.reload();
    await expect(page.getByTestId("streak-tile")).toContainText("Start a streak", {
      timeout: 15_000,
    });
  });

  test("container_resize_moves_rail_from_row_to_aside", async ({ page }) => {
    await seedBrowser(page, []);
    await page.setViewportSize({ width: 1400, height: 900 });
    await page.goto("/learn");
    const root = page.getByTestId("dashboard-root");
    await expect(root).toBeVisible({ timeout: 15_000 });
    await expectNoAxeViolations(page);

    // FR-1: container-type must be present (falsifiable).
    const containerType = await root.evaluate(
      (el) => getComputedStyle(el).containerType,
    );
    expect(containerType).toBe("inline-size");

    const rail = page.getByTestId("trust-rail");
    const buckets = page.getByLabel("Skill mastery");

    await root.evaluate((el) => {
      (el as HTMLElement).style.maxWidth = "380px";
    });
    // Narrow: rail sits below the mastery grid (row layout).
    const narrowRail = await rail.boundingBox();
    const narrowBuckets = await buckets.boundingBox();
    expect(narrowRail).toBeTruthy();
    expect(narrowBuckets).toBeTruthy();
    expect(narrowRail!.y).toBeGreaterThan(narrowBuckets!.y);

    await root.evaluate((el) => {
      (el as HTMLElement).style.maxWidth = "1280px";
    });
    // Wide: rail sits to the right of the mastery grid (aside layout).
    const wideRail = await rail.boundingBox();
    const wideBuckets = await buckets.boundingBox();
    expect(wideRail).toBeTruthy();
    expect(wideBuckets).toBeTruthy();
    expect(wideRail!.x).toBeGreaterThan(wideBuckets!.x);
  });

  test("retry_button_re_fires_read_after_transient_error", async ({ page }) => {
    // Fail-once via composition-root decorator (env + ?e2e_rail_fail=1).
    await seedBrowser(page, []);
    await page.goto("/learn?e2e_rail_fail=1");
    await expect(page.getByText("Trust rail unavailable")).toBeVisible({
      timeout: 15_000,
    });
    await expectNoAxeViolations(page);
    await expect(page.getByTestId("rail-retry")).toBeVisible();
    await page.getByTestId("rail-retry").click();
    await expect(page.getByTestId("streak-tile")).toContainText("Start a streak", {
      timeout: 15_000,
    });
    await expect(page.getByText("Trust rail unavailable")).toHaveCount(0);
  });

  test("retry_button_is_rail_scoped", async ({ page }) => {
    await seedBrowser(page, []);
    await page.goto("/learn?e2e_rail_fail=1");
    await expect(page.getByText("Trust rail unavailable")).toBeVisible({
      timeout: 15_000,
    });
    await expectNoAxeViolations(page);
    const greeting = page.getByTestId("dashboard-greeting");
    await expect(greeting).toBeVisible();
    const greetingHandle = await greeting.elementHandle();
    expect(greetingHandle).toBeTruthy();

    await page.getByTestId("rail-retry").click();
    await expect(page.getByTestId("streak-tile")).toBeVisible({
      timeout: 15_000,
    });

    // FR-8: same greeting node stays connected across rail retry.
    expect(await greetingHandle!.evaluate((el) => el.isConnected)).toBe(true);
    await expect(greeting).toBeVisible();
  });
});
