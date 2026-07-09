/**
 * E2E — the done-state milestone + retake on the /learn quiz (S5).
 *
 * Closes the DONE-STATE half of the reported "/learn is an infinite loop" gap (S4
 * shipped the progress bar; S5 is "you've reached your goal"). When the graded
 * tally reaches the session target, a milestone banner appears ABOVE the item's
 * feedback and the two actions read "Keep practising" / "See summary" — the learner
 * gets a sense of completion and a NON-TRAPPING choice, never a force-eject.
 *
 * The "reached?" decision is the pure translator (`quiz_progress_vm.complete`,
 * unit-tested); this spec proves the wired behaviour a user sees in a real browser:
 *   - FR-4/FR-5: at the boundary (Question 30 of 30, reviewing) the banner shows and
 *     names the count; it is a SIBLING ABOVE the feedback (both visible).
 *   - FR-3: reaching the target does NOT auto-navigate — still on /learn/quiz.
 *   - FR-2/FR-7: "Keep practising" continues the SAME session; the bar goes into
 *     over-run (true position past 30, denominator dropped — reuses S4 rendering).
 *   - FR-6: "See summary" closes + routes to the Summary with the stored score.
 *   - Gate-2 (unconditional relabel): the buttons read the new labels on a
 *     PRE-target screen too, not only at the boundary.
 *
 * L4 Behavioral Validation: real browser against the dev-seeded bank quiz (the
 * `learn-e2e` project, video on), on-demand only — pure T1 (seeded browser engine,
 * no backend/auth/LLM). Cost note: no short-target seed hook exists (the E2E seed
 * carries the CORPUS, not session `target_count`), so this walks the full 30-item
 * session to the boundary, like the sibling `quiz-progress.spec.ts`.
 *
 * Run: `npx playwright test --project=learn-e2e e2e/learn/quiz-done-state.spec.ts`
 */

import { test, expect, type Page } from "@playwright/test";

/** The seed floor: `DrizzleSessionRepo.DEFAULT_TARGET_COUNT` with no policy row. */
const TARGET = 30;

/** The progress region's rendered counter text ("Question N of M"), or "" if absent. */
async function counterText(page: Page): Promise<string> {
  const el = page.locator("[data-testid='quiz-progress']");
  if ((await el.count()) === 0) return "";
  return (await el.textContent())?.trim() ?? "";
}

/** Answer the current item (A → Submit) and STOP on the feedback screen. */
async function answerToFeedback(page: Page): Promise<void> {
  await page.locator("[data-testid='choice-A']").click();
  await page.locator("[data-testid='quiz-submit']").click();
  await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
    timeout: 10_000,
  });
}

/** From a feedback screen, press "Keep practising" and wait for the next item. */
async function keepPractising(page: Page): Promise<void> {
  await page.locator("[data-testid='quiz-next']").click();
  await page.locator("[data-skill]").first().waitFor({ timeout: 10_000 });
}

/** Answer the current item and advance to the next (feedback → keep practising). */
async function answerAndAdvance(page: Page): Promise<void> {
  await answerToFeedback(page);
  await keepPractising(page);
}

test.describe("Quiz done-state — milestone + retake (S5)", () => {
  test("pre-target screens keep the ORIGINAL labels (relabel gated on the target)", async ({
    page,
  }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip((await counterText(page)) === "", "Skipped: quiz not rendered (auth/env).");

    // Answer item 1 and stop on feedback — WELL before the target.
    await answerToFeedback(page);

    // Reverted 2026-07-09 (user): the buttons keep their ORIGINAL labels
    // ("Next question" / "Finish & see summary") until the target is reached; the
    // S5 labels ("Keep practising" / "See summary") appear ONLY at/after the target,
    // alongside the milestone banner. So this early the banner is absent AND the
    // labels are the originals.
    await expect(page.locator("[data-testid='quiz-next']")).toHaveText(/Next question/);
    await expect(page.locator("[data-testid='quiz-finish']")).toHaveText(/Finish & see summary/);
    await expect(page.locator("[data-testid='quiz-done-banner']")).toHaveCount(0);
  });

  test("reaching the target shows the milestone and does NOT auto-navigate (FR-3/FR-4/FR-5)", async ({
    page,
  }) => {
    test.setTimeout(180_000); // a 30-item walk to the boundary needs headroom
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip((await counterText(page)) === "", "Skipped: quiz not rendered (auth/env).");
    expect(await counterText(page)).toContain(`Question 1 of ${TARGET}`);

    // Walk the first 29 items to completion; each advance moves the counter +1.
    // After 29 graded+advanced, the answering screen reads "Question 30 of 30".
    for (let i = 0; i < TARGET - 1; i += 1) {
      await answerAndAdvance(page);
    }
    expect(await counterText(page)).toContain(`Question ${TARGET} of ${TARGET}`);
    // Not yet reached (still answering #30) — no banner before it is graded.
    await expect(page.locator("[data-testid='quiz-done-banner']")).toHaveCount(0);

    // Grade the 30th item → reviewing with gradedTotal == target → complete.
    await answerToFeedback(page);

    // FR-4/FR-5: the milestone banner is now visible, names the count, and is a
    // SIBLING ABOVE the feedback (both present — the learner still sees #30's answer).
    const banner = page.locator("[data-testid='quiz-done-banner']");
    await expect(banner).toBeVisible();
    await expect(banner).toContainText(String(TARGET)); // "…your 30-question session!"
    await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible();

    // The labels now FLIP to the S5 versions at the target (reverted 2026-07-09:
    // gated on `complete`, not unconditional) — same testids, new text.
    await expect(page.locator("[data-testid='quiz-next']")).toHaveText(/Keep practising/);
    await expect(page.locator("[data-testid='quiz-finish']")).toHaveText(/See summary/);

    // FR-5 placement: banner precedes the feedback in DOM order (rendered above it).
    const order = await page.evaluate(() => {
      const done = document.querySelector('[data-testid="quiz-done-banner"]');
      const fb = document.querySelector('[data-testid="feedback-banner"]');
      if (!done || !fb) return "missing";
      // bitmask 4 = done FOLLOWS fb; we want done BEFORE fb (bitmask 2).
      return done.compareDocumentPosition(fb) & Node.DOCUMENT_POSITION_FOLLOWING ? "done-before-fb" : "fb-before-done";
    });
    expect(order).toBe("done-before-fb");

    // FR-3: reaching the target did NOT eject the learner — still on the quiz.
    expect(page.url()).toContain("/learn/quiz");
  });

  test("'Keep practising' continues the same session into over-run (FR-2/FR-7)", async ({
    page,
  }) => {
    test.setTimeout(180_000);
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip((await counterText(page)) === "", "Skipped: quiz not rendered (auth/env).");

    // Reach the boundary (grade all 30), then continue.
    for (let i = 0; i < TARGET - 1; i += 1) await answerAndAdvance(page);
    await answerToFeedback(page); // 30th graded → done-state
    await expect(page.locator("[data-testid='quiz-done-banner']")).toBeVisible();

    // FR-7: "Keep practising" continues the SAME session (no re-open). The next item
    // is #31 → over-run: S4 renders the true position and DROPS the "of M" denominator.
    await keepPractising(page);
    const text = await counterText(page);
    expect(text).toContain("Question 31");
    expect(text).not.toContain(` of ${TARGET}`); // denominator dropped past target
  });

  test("'See summary' closes the session and routes to the Summary (FR-6)", async ({
    page,
  }) => {
    test.setTimeout(180_000);
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip((await counterText(page)) === "", "Skipped: quiz not rendered (auth/env).");

    for (let i = 0; i < TARGET - 1; i += 1) await answerAndAdvance(page);
    await answerToFeedback(page); // 30th graded → done-state
    await expect(page.locator("[data-testid='quiz-done-banner']")).toBeVisible();

    // FR-6: "See summary" (the relabelled Finish control) closes + routes to Summary.
    await page.locator("[data-testid='quiz-finish']").click();
    await page.waitForURL(/\/learn\/summary/, { timeout: 10_000 });
    expect(page.url()).toContain("/learn/summary");
    // The stored score renders (Summary never re-tallies) — the session param rode over.
    expect(page.url()).toContain("session=");
  });
});
