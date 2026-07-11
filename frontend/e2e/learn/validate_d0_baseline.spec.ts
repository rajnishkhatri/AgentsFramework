/**
 * VALIDATION WALK — Sprint D0 (correct the record) → post-D1 continuity.
 *
 * D0 was docs-only (corrected five Epic D framings). D1 has since shipped
 * Q-7 / Q-8 / Q-9 session-frame chrome. This walk now proves:
 *
 *   1. Core Quiz answering chrome still works (regression).
 *   2. D1 session-frame affordances are PRESENT (skill chip / end-session /
 *      timer reveal) — detailed behaviour lives in `quiz-frame.spec.ts`.
 *   3. D-8 "Skills" nav is NOT in membership (still deferred to Epic E).
 *
 * Spec: docs/plan/preact-parity-D0-correct-record.spec.md
 * D1 L4: e2e/learn/quiz-frame.spec.ts
 *
 * Run (against a running bypass-auth dev server on :3000):
 *   E2E_SCREENSHOTS=1 CI=1 BASE_URL=http://localhost:3000 \
 *     pnpm test:e2e:d0-baseline
 */

import { test, expect } from "@playwright/test";

test("D0→D1 continuity — frame chrome present; Skills nav still absent", async ({
  page,
}, testInfo) => {
  test.setTimeout(60_000);

  const log = (msg: string) => console.log(`  ✔ ${msg}`);
  const shot = async (name: string) => {
    if (process.env.E2E_SCREENSHOTS !== "1") return;
    const buf = await page.screenshot();
    await testInfo.attach(name, { body: buf, contentType: "image/png" });
  };

  // --- Dashboard: nav membership (D-8 still deferred) -----------------------
  await page.goto("/learn", { waitUntil: "networkidle" });
  await expect(page.locator("[data-testid='today-focus']")).toBeVisible({
    timeout: 15_000,
  });

  const nav = page.locator('nav[aria-label="Primary"]');
  await expect(nav).toBeVisible();
  const navLabels = (await nav.locator("[data-screen]").allTextContents()).map(
    (t) => t.trim(),
  );
  expect(navLabels).toEqual(
    expect.arrayContaining(["Home", "Practice", "Coach", "Progress"]),
  );
  expect(navLabels.some((l) => /skills?/i.test(l))).toBe(false);
  await expect(nav.locator('[data-screen="skill"]')).toHaveCount(0);
  log("D-8 baseline: sidebar has Home/Practice/Coach/Progress — no Skills entry");
  await shot("01-dashboard-nav-no-skills");

  // --- Quiz answering: core chrome present ----------------------------------
  await page.goto("/learn/quiz", { waitUntil: "networkidle" });
  await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.locator("[data-testid='quiz-progress']")).toBeVisible();
  await expect(page.locator("[data-testid='choice-A']")).toBeVisible();
  await expect(page.locator("[data-testid='quiz-submit']")).toBeVisible();
  await expect(page.locator("[data-testid='quiz-reveal']")).toBeVisible();
  await expect(page.locator("[data-testid='quiz-hint-toggle']")).toBeVisible();
  log("core Quiz answering chrome present (progress / choices / submit / reveal / hint)");

  // --- D1 affordances PRESENT (shipped by Sprint D1) ------------------------
  await expect(page.locator("[data-testid='quiz-skill-chip']")).toHaveCount(1);
  await expect(page.locator("[data-testid='quiz-end-session']")).toHaveCount(1);
  await expect(page.locator("[data-testid='quiz-timer-reveal']")).toHaveCount(1);
  await expect(page.locator("[data-testid='quiz-timer']")).toHaveCount(0);
  log("Q-7/Q-8/Q-9: skill chip + End session + collapsed timer present");
  await shot("02-quiz-d1-frame-chrome");

  // --- Smoke: select + submit still reaches Feedback ------------------------
  await page.locator("[data-testid='choice-A']").click();
  await expect(page.locator("[data-testid='quiz-submit']")).toBeEnabled();
  await page.locator("[data-testid='quiz-submit']").click();
  await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
    timeout: 15_000,
  });
  log("regression: Submit → Feedback still works");
  await shot("03-feedback-after-submit");

  console.log(
    "  D0→D1 continuity PASSED — frame chrome present; D-8 Skills still deferred.",
  );
});
