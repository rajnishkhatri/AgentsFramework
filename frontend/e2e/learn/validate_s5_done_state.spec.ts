/**
 * VALIDATION WALK — S5 done-state + retake (/learn quiz), per-FR narrated.
 *
 * A companion to the assertion spec `quiz-done-state.spec.ts`. Where that spec
 * splits the checks across four independent tests (fast, isolated), THIS is ONE
 * continuous walk that mirrors how a human validates on localhost: open the quiz,
 * answer through to the target, watch the milestone appear, continue into
 * over-run, then exit to the Summary — logging each FR checkpoint as it passes and
 * capturing a screenshot at the three states that matter. Run it to WATCH S5 work
 * end-to-end (the `learn-e2e` project records video too).
 *
 * Every checkpoint maps to a spec FR (docs/plan/preact-quiz-done-state.spec.md):
 *   FR-4/FR-5  milestone at the boundary, above feedback, names the count
 *   FR-3       reaching the target does NOT auto-navigate
 *   FR-7/FR-2  "Keep practising" continues the SAME session into over-run
 *   FR-6       "See summary" closes + routes to the Summary with the score
 *   labels     original ("Next question" / "Finish & see summary") pre-target;
 *              flip to "Keep practising" / "See summary" only at/after the target
 *
 * Artifacts (screenshots) land next to the video under
 *   test-results/<slug>/  — see the .md walkthrough for how to open them.
 * Force the per-step screenshots with E2E_SCREENSHOTS=1.
 *
 * Run (against a running bypass-auth dev server on :3000):
 *   E2E_SCREENSHOTS=1 CI=1 BASE_URL=http://localhost:3000 \
 *     ./node_modules/.bin/playwright test --project=learn-e2e \
 *     e2e/learn/validate_s5_done_state.spec.ts --reporter=list
 */

import { test, expect, type Page } from "@playwright/test";

/** The seed floor: DrizzleSessionRepo.DEFAULT_TARGET_COUNT with no policy row. */
const TARGET = 30;

async function counterText(page: Page): Promise<string> {
  const el = page.locator("[data-testid='quiz-progress']");
  if ((await el.count()) === 0) return "";
  return (await el.textContent())?.trim() ?? "";
}

/** Answer the current item (A → Submit) and STOP on the feedback screen. */
async function answerToFeedback(page: Page): Promise<void> {
  await page.locator("[data-testid='choice-A']").click();
  await page.locator("[data-testid='quiz-submit']").click();
  await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({ timeout: 10_000 });
}

/** From feedback, press "Keep practising" (quiz-next) and wait for the next item. */
async function keepPractising(page: Page): Promise<void> {
  await page.locator("[data-testid='quiz-next']").click();
  await page.locator("[data-skill]").first().waitFor({ timeout: 10_000 });
}

test("S5 validation walk — target → milestone → over-run → summary", async ({ page }, testInfo) => {
  test.setTimeout(180_000); // a 30-item walk to the boundary needs headroom

  const log = (msg: string) => console.log(`  ✔ ${msg}`);
  // Attach a screenshot to the HTML report AND write a named file beside the video.
  const shot = async (name: string) => {
    const buf = await page.screenshot();
    await testInfo.attach(name, { body: buf, contentType: "image/png" });
  };

  await page.goto("/learn/quiz", { waitUntil: "networkidle" });
  test.skip((await counterText(page)) === "", "Skipped: quiz not rendered (auth/env).");
  expect(await counterText(page)).toContain(`Question 1 of ${TARGET}`);
  log(`opened /learn/quiz → "${await counterText(page)}"`);

  // --- Pre-target: the actions keep their ORIGINAL labels --------------------
  await answerToFeedback(page);
  await expect(page.locator("[data-testid='quiz-next']")).toHaveText(/Next question/);
  await expect(page.locator("[data-testid='quiz-finish']")).toHaveText(/Finish & see summary/);
  await expect(page.locator("[data-testid='quiz-done-banner']")).toHaveCount(0);
  await shot("01-pre-target-feedback");
  log('pre-target: buttons read "Next question" / "Finish & see summary"; NO banner yet');
  await keepPractising(page);

  // --- Walk the rest of the way to the target (items 2..30) ------------------
  // We already graded item 1; grade+advance items 2..29, then grade item 30.
  for (let i = 2; i <= TARGET - 1; i += 1) {
    await answerToFeedback(page);
    await keepPractising(page);
  }
  expect(await counterText(page)).toContain(`Question ${TARGET} of ${TARGET}`);
  await expect(page.locator("[data-testid='quiz-done-banner']")).toHaveCount(0);
  log(`walked to "${await counterText(page)}" (answering #${TARGET}) — still no banner (FR-4: only after grading)`);

  // Grade the 30th → reviewing with gradedTotal == target → complete.
  await answerToFeedback(page);

  // --- FR-4/FR-5: milestone at the boundary, above feedback, names the count -
  const banner = page.locator("[data-testid='quiz-done-banner']");
  await expect(banner).toBeVisible();
  await expect(banner).toContainText(String(TARGET));
  await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible();
  const order = await page.evaluate(() => {
    const done = document.querySelector('[data-testid="quiz-done-banner"]');
    const fb = document.querySelector('[data-testid="feedback-banner"]');
    if (!done || !fb) return "missing";
    return done.compareDocumentPosition(fb) & Node.DOCUMENT_POSITION_FOLLOWING ? "done-before-fb" : "fb-before-done";
  });
  expect(order).toBe("done-before-fb");
  // The labels FLIP to the S5 versions at the target (in lock-step with the banner).
  await expect(page.locator("[data-testid='quiz-next']")).toHaveText(/Keep practising/);
  await expect(page.locator("[data-testid='quiz-finish']")).toHaveText(/See summary/);
  await shot("02-boundary-milestone");
  log(`FR-4/FR-5: milestone visible at Q${TARGET}, ABOVE feedback, names "${TARGET}"; labels flip to Keep practising / See summary`);

  // --- FR-3: reaching the target did NOT auto-navigate ----------------------
  expect(page.url()).toContain("/learn/quiz");
  log("FR-3: still on /learn/quiz — no force-eject");

  // --- FR-7/FR-2: "Keep practising" continues into over-run -----------------
  await keepPractising(page);
  const overrun = await counterText(page);
  expect(overrun).toContain("Question 31");
  expect(overrun).not.toContain(` of ${TARGET}`); // denominator dropped past target
  await shot("03-over-run");
  log(`FR-7/FR-2: "Keep practising" → same session over-run → "${overrun}" (denominator dropped)`);

  // --- FR-6: "See summary" closes + routes to the Summary -------------------
  // Grade one more over-run item so a feedback screen with the control is present.
  await answerToFeedback(page);
  await page.locator("[data-testid='quiz-finish']").click();
  await page.waitForURL(/\/learn\/summary/, { timeout: 10_000 });
  expect(page.url()).toContain("/learn/summary");
  expect(page.url()).toContain("session=");
  await shot("04-summary");
  log(`FR-6: "See summary" → ${new URL(page.url()).pathname} with the stored score`);

  console.log("\n  S5 validation walk PASSED — all FR checkpoints green.\n");
});
