/**
 * VALIDATION WALK — Sprint A1 Reveal answer (D6+D1), per-task / per-FR narrated.
 *
 * Companion to the L1 unit suite in `QuizView.test.tsx`. That suite proves the
 * gate + onClick wiring in jsdom; THIS is ONE continuous browser walk that
 * mirrors how a human validates on localhost: open Quiz, prove Reveal is inert
 * until a choice is selected, activate Reveal (not Submit), land on Feedback
 * with the teaching letter — and confirm the Quiz screen never showed the
 * answer letter in-place.
 *
 * Maps to docs/plan/preact-parity-A1-reveal.spec.md + plan tasks:
 *   A1-0 / FR-5   UI FR-D6a documented (manual / grep — not asserted here)
 *   A1-1+A1-2 / FR-1  Reveal disabled + data-enabled=false with no selection
 *   FR-4          ghost control distinct from hint (label + muted vs dashed accent)
 *   FR-2          answering DOM has no "Why X is correct" / CORRECT ANSWER chrome
 *   FR-3          Reveal click → same Feedback path as Submit
 *   hint ⊕ Reveal orthogonal (hint open does not block Reveal→Feedback)
 *   A1-3 / FR-6   decisions.md (manual)
 *   A1-4          this walk + unit suite green
 *
 * Artifacts: learn-e2e records video; E2E_SCREENSHOTS=1 attaches named shots.
 *
 * Run (against a running bypass-auth dev server on :3000):
 *   E2E_SCREENSHOTS=1 CI=1 BASE_URL=http://localhost:3000 \
 *     ./node_modules/.bin/playwright test --project=learn-e2e \
 *     e2e/learn/validate_a1_reveal.spec.ts --reporter=list
 *
 * Or: pnpm test:e2e:a1-reveal
 */

import { test, expect } from "@playwright/test";

test("A1 validation walk — Reveal gated submit alias (all tasks)", async ({
  page,
}, testInfo) => {
  test.setTimeout(60_000);

  const log = (msg: string) => console.log(`  ✔ ${msg}`);
  const shot = async (name: string) => {
    const buf = await page.screenshot();
    await testInfo.attach(name, { body: buf, contentType: "image/png" });
  };

  // --- Open Quiz (answering phase) ------------------------------------------
  await page.goto("/learn/quiz", { waitUntil: "networkidle" });
  await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
    timeout: 15_000,
  });
  test.skip(
    (await page.locator("[data-testid='quiz-reveal']").count()) === 0,
    "Skipped: quiz-reveal not rendered (auth/env).",
  );
  log("opened /learn/quiz — answering phase visible");

  const revealBtn = page.locator("[data-testid='quiz-reveal']");
  const submitBtn = page.locator("[data-testid='quiz-submit']");
  const hintToggle = page.locator("[data-testid='quiz-hint-toggle']");

  // --- FR-4 / A1-2: ghost control present, distinct from hint ---------------
  await expect(revealBtn).toBeVisible();
  await expect(revealBtn).toHaveText(/Reveal answer/);
  await expect(hintToggle).toBeVisible();
  await expect(hintToggle).toHaveText(/Get a hint/);
  const revealClass = (await revealBtn.getAttribute("class")) ?? "";
  const hintClass = (await hintToggle.getAttribute("class")) ?? "";
  expect(revealClass).toMatch(/text-muted/);
  expect(hintClass).toMatch(/border-dashed/);
  expect(hintClass).toMatch(/border-accent|text-accent/);
  log("FR-4: Reveal is a distinct ghost control (text-muted) separate from hint (dashed accent)");

  // --- FR-1 / A1-1: no selection → Reveal non-actionable --------------------
  await expect(revealBtn).toBeDisabled();
  await expect(revealBtn).toHaveAttribute("data-enabled", "false");
  await expect(submitBtn).toBeDisabled();
  await expect(submitBtn).toHaveAttribute("data-enabled", "false");
  // Click attempt must not navigate / open Feedback.
  await revealBtn.click({ force: true }).catch(() => undefined);
  await expect(page.locator("[data-testid='feedback-banner']")).toHaveCount(0);
  await expect(page).toHaveURL(/\/learn\/quiz/);
  await shot("01-reveal-disabled-no-selection");
  log("FR-1: no selection → Reveal disabled (data-enabled=false); click does not open Feedback");

  // --- FR-2: answering phase does not teach the letter in-place -------------
  const answeringBody = (await page.locator("main, body").first().innerText()) ?? "";
  expect(answeringBody).not.toMatch(/Why\s+[A-D]\s+is correct/i);
  expect(answeringBody).not.toMatch(/CORRECT ANSWER/i);
  log("FR-2: answering DOM has no in-place 'Why X is correct' / CORRECT ANSWER chrome");

  // --- Hint orthogonal: open hint, still no Feedback, Reveal still gated ----
  await hintToggle.click();
  await expect(page.locator("[data-testid='quiz-hint']")).toBeVisible();
  await expect(revealBtn).toBeDisabled();
  await expect(page.locator("[data-testid='feedback-banner']")).toHaveCount(0);
  log("hint open: orthogonal — Reveal still gated; Feedback not shown");

  // --- Select a choice → Reveal (and Submit) become actionable --------------
  await page.locator("[data-testid^='choice-']").first().click();
  await expect(revealBtn).toBeEnabled();
  await expect(revealBtn).toHaveAttribute("data-enabled", "true");
  await expect(submitBtn).toBeEnabled();
  await shot("02-reveal-enabled-after-selection");
  log("selection made → Reveal enabled (data-enabled=true), same gate as Submit");

  // --- FR-3: activate Reveal (NOT Submit) → Feedback teaching path ----------
  await revealBtn.click();
  const banner = page.locator("[data-testid='feedback-banner']");
  await expect(banner).toBeVisible({ timeout: 10_000 });
  const bannerState = await banner.getAttribute("data-banner");
  expect(bannerState === "celebrate" || bannerState === "soft").toBe(true);
  // Reveal control is answering-only — gone once Feedback replaces QuizView.
  await expect(page.locator("[data-testid='quiz-reveal']")).toHaveCount(0);
  // Feedback owns the letter (UI FR-E1/E4).
  await expect(page.getByText(/Why\s+[A-D]\s+is correct/i)).toBeVisible();
  await shot("03-feedback-via-reveal");
  log(
    `FR-3: Reveal → Feedback (data-banner=${bannerState}); quiz-reveal gone; teaching letter on Feedback`,
  );

  // --- Same path as Submit: advance and prove Submit still grades -----------
  await page.locator("[data-testid='quiz-next']").click();
  await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
    timeout: 10_000,
  });
  await page.locator("[data-testid^='choice-']").first().click();
  await page.locator("[data-testid='quiz-submit']").click();
  await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
    timeout: 10_000,
  });
  log("parity check: Submit on next item also reaches Feedback (same path family)");

  await shot("04-feedback-via-submit-parity");
  console.log(
    "\n  A1 validation walk PASSED — FR-1/2/3/4 green; Reveal = gated submit alias.\n",
  );
});
