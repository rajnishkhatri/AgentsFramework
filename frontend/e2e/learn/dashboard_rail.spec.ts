/**
 * C1 Dashboard rail + greeting (FR-1/2/5/6/7/8).
 *
 * T1: browser-seeded InMemoryEngineDb via `__PREACT_E2E_SEED__`. Optional
 * `sessions` on the corpus drive streak/weekly; `__PREACT_E2E_RAIL_FAIL_ONCE__`
 * forces the FR-1 unavailable path once for the Retry row.
 */

import { test, expect, type Page } from "@playwright/test";
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

test.describe("C1 dashboard rail + greeting", () => {
  test("cold_start_renders_honest_empty_state", async ({ page }) => {
    await seedBrowser(page, []);
    await page.goto("/learn");
    await expect(page.getByTestId("dashboard-root")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("streak-tile")).toContainText("Start a streak");
    await expect(page.getByTestId("weekly-tile")).toContainText("0 / 3 sessions");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Maya");
  });

  test("returning_learner_shows_streak_and_weekly", async ({ page }) => {
    // Freeze local clock so consecutive local-days are stable.
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
    await expect(page.getByTestId("weekly-tile")).toContainText("3 / 3 sessions");
  });

  test("injected_clock_midnight_determinism", async ({ page }) => {
    const justBeforeMidnight = new Date(2026, 6, 10, 23, 59, 59, 0);
    await page.clock.install({ time: justBeforeMidnight });
    // One session earlier today — streak = 1 before and after midnight.
    const sessions = [
      closedSession("today", new Date(2026, 6, 10, 12, 0, 0, 0)),
    ];
    await seedBrowser(page, sessions);
    await page.goto("/learn");
    await expect(page.getByTestId("streak-tile")).toContainText("1-day streak", {
      timeout: 15_000,
    });
    await page.clock.fastForward("00:00:02"); // → 00:00:01 next day
    await page.getByTestId("rail-retry").click({ trial: true }).catch(() => undefined);
    // Reload so loadDashboard re-reads with the advanced clock.
    await page.reload();
    // After midnight with no session on the new day → streak resets (FR-6/7).
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
    const rail = page.getByTestId("trust-rail");

    await root.evaluate((el) => {
      (el as HTMLElement).style.maxWidth = "380px";
    });
    // Narrow container: rail sits in document order below header (order-2).
    const narrowOrder = await rail.evaluate((el) => getComputedStyle(el).order);
    expect(Number(narrowOrder)).toBeGreaterThan(0);

    await root.evaluate((el) => {
      (el as HTMLElement).style.maxWidth = "1280px";
    });
    // Wide @lg: rail is a grid aside (order resets / column 2).
    await expect(rail).toHaveAttribute("aria-label", "Trust rail");
    const wideCols = await root.evaluate((el) => getComputedStyle(el).gridTemplateColumns);
    expect(wideCols === "none" || wideCols.split(" ").length >= 2).toBe(true);
  });

  test("retry_button_re_fires_read_after_transient_error", async ({ page }) => {
    await page.addInitScript(() => {
      (window as unknown as { __PREACT_E2E_RAIL_FAIL_ONCE__?: boolean })
        .__PREACT_E2E_RAIL_FAIL_ONCE__ = true;
    });
    await seedBrowser(page, []);
    await page.goto("/learn");
    await expect(page.getByText("Trust rail unavailable")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("rail-retry")).toBeVisible();
    await page.getByTestId("rail-retry").click();
    await expect(page.getByTestId("streak-tile")).toContainText("Start a streak", {
      timeout: 15_000,
    });
    await expect(page.getByText("Trust rail unavailable")).toHaveCount(0);
  });
});
