/**
 * E2E — v3 "commit-first" EARS spec conformance on /learn/quiz.
 *
 * Derived requirement-by-requirement from the DESIGN-AGENT spec:
 *   docs/plan/gen2-proto-handoff/03-ears-spec-gen2-coach-v3.md
 * App-scoped: requirements the app spec (docs/plan/commit-first-coach.spec.md
 * §10) explicitly excludes (TRACE rail, LEAK regex, SUM-2 chips, SEQ-1 fixed
 * order, MOM-7 stub) are NOT tested here. Everything else from the v3 spec is.
 * A failing test here = a prototype↔implementation gap for the replan board.
 *
 * Requires flag ON (webServer defaults it OFF for legacy specs):
 *   NEXT_PUBLIC_FF_COMMIT_FIRST_COACH=1 E2E_BYPASS_AUTH=1 \
 *     npx playwright test --project=learn-e2e e2e/learn/quiz-commit-first-v3-spec.spec.ts
 */

import { test, expect, type Page } from "@playwright/test";

const LETTERS = ["A", "B", "C", "D"] as const;

async function quizReady(page: Page): Promise<boolean> {
  await page.goto("/learn/quiz", { waitUntil: "networkidle" });
  const progress = page.locator("[data-testid='quiz-progress']");
  if ((await progress.count()) === 0) return false;
  return (await page.locator("[data-testid='quiz-hint-toggle']").count()) === 0;
}

/** Submit letters until one lands wrong (coached section appears). Returns the wrong letter, or null if everything solved. */
async function reachCoachedLoop(page: Page): Promise<string | null> {
  for (let item = 0; item < 3; item++) {
    for (const letter of ["A", "B"]) {
      const choice = page.locator(`[data-testid='choice-${letter}']`);
      if ((await choice.count()) === 0) continue;
      await choice.click();
      await page.locator("[data-testid='quiz-submit']").click();
      const coached = page.locator("[data-testid='quiz-coached-section']");
      const feedback = page.locator("[data-testid='feedback-banner']");
      await Promise.race([
        coached.waitFor({ state: "visible", timeout: 10_000 }).catch(() => {}),
        feedback.waitFor({ state: "visible", timeout: 10_000 }).catch(() => {}),
      ]);
      if (await coached.isVisible()) return letter;
      if (await feedback.isVisible()) {
        await page.locator("[data-testid='quiz-next']").click();
        await page
          .locator("[data-testid='quiz-submit']")
          .waitFor({ timeout: 10_000 });
        break; // fresh item; try letters again
      }
    }
  }
  return null;
}

test.describe("v3 spec — idle moment (MOM-1 / MOM-9 / CTRL-1 / DAT-5)", () => {
  test("MOM-1/MOM-9: idle has no hint affordance, no ladder rail, no counter", async ({
    page,
  }) => {
    test.skip(!(await quizReady(page)), "quiz not rendered or flag OFF");
    await expect(page.locator("[data-testid='quiz-hint-toggle']")).toHaveCount(0);
    await expect(page.locator("[data-testid='quiz-coached-section']")).toHaveCount(0);
    await expect(page.locator("[data-testid='quiz-rung-counter']")).toHaveCount(0);
    await expect(page.locator("[data-testid='one-more-nudge']")).toHaveCount(0);
  });

  test("CTRL-1: Submit disabled before a choice; idle copy promises no pre-pick help", async ({
    page,
  }) => {
    test.skip(!(await quizReady(page)), "quiz not rendered or flag OFF");
    await expect(page.locator("[data-testid='quiz-submit']")).toBeDisabled();
    await expect(
      page.locator("[data-testid='quiz-commit-idle-hint']"),
    ).toContainText(/no hints until you commit/i);
  });

  test("ESC-3/FR-1: no 'Reveal answer' affordance exists anywhere", async ({
    page,
  }) => {
    test.skip(!(await quizReady(page)), "quiz not rendered or flag OFF");
    await expect(page.locator("[data-testid='quiz-reveal']")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /reveal answer/i })).toHaveCount(0);
  });
});

test.describe("v3 spec — wrong-pick moment (MOM-3 / MOM-4 / VOICE-1 / CTRL-2)", () => {
  test("MOM-3: wrong submit stays un-revealed and shows rung 1 (pump)", async ({
    page,
  }) => {
    test.skip(!(await quizReady(page)), "quiz not rendered or flag OFF");
    const wrong = await reachCoachedLoop(page);
    test.skip(wrong == null, "could not reach a wrong pick in 3 items");
    await expect(page.locator("[data-testid='feedback-banner']")).toHaveCount(0);
    await expect(page.locator("[data-testid='quiz-rung-1']")).toBeVisible();
    await expect(page.locator("[data-testid='quiz-rung-counter']")).toHaveText("1 of 3");
  });

  test("MOM-3/VOICE-1: wrong pick is ACKNOWLEDGED (shared ground) before the pump", async ({
    page,
  }) => {
    // v3 MOM-3: "acknowledge (shared-ground first ...) then reveal ladder rung 1".
    // The acknowledgment is a distinct coach statement, not the pump question itself.
    test.skip(!(await quizReady(page)), "quiz not rendered or flag OFF");
    const wrong = await reachCoachedLoop(page);
    test.skip(wrong == null, "could not reach a wrong pick in 3 items");
    const ack = page.locator(
      "[data-testid='quiz-coached-ack'], [data-testid='coach-acknowledgment']",
    );
    await expect(ack).toBeVisible({ timeout: 3_000 });
    // T19 / V1: pick echo is its own learner turn before the ack.
    await expect(page.locator("[data-testid='quiz-pick-echo']")).toHaveText(
      `I chose ${wrong}.`,
    );
  });

  test("MOM-4/CTRL-2: honest n-of-3 counter, escalating CTA labels, letter-named footnote", async ({
    page,
  }) => {
    test.skip(!(await quizReady(page)), "quiz not rendered or flag OFF");
    const wrong = await reachCoachedLoop(page);
    test.skip(wrong == null, "could not reach a wrong pick in 3 items");
    const counter = page.locator("[data-testid='quiz-rung-counter']");
    const nudge = page.locator("[data-testid='quiz-nudge']");
    await expect(counter).toHaveText("1 of 3");
    await expect(
      page.locator("[data-testid='quiz-nudge-footnote']"),
    ).toContainText(`your pick of ${wrong}`);
    await expect(nudge).toHaveText("Show me more →");
    await nudge.click();
    await expect(counter).toHaveText("2 of 3");
    // V6 / T19: stuck phrase is a user-echo turn, not the button label.
    await expect(nudge).toHaveText("Show me more →");
    await expect(
      page.locator("[data-testid='quiz-stuck-echo-2']"),
    ).toHaveText("I'm still stuck.");
    await nudge.click();
    await expect(counter).toHaveText("3 of 3");
  });

  test("MOM-4/ESC-2: exhaustion = exact copy, exactly two actions, priced escape", async ({
    page,
  }) => {
    test.skip(!(await quizReady(page)), "quiz not rendered or flag OFF");
    const wrong = await reachCoachedLoop(page);
    test.skip(wrong == null, "could not reach a wrong pick in 3 items");
    const nudge = page.locator("[data-testid='quiz-nudge']");
    await nudge.click();
    await nudge.click();
    await expect(page.locator("[data-testid='quiz-exhaustion-copy']")).toContainText(
      /all three nudges .* never tell the answer/i,
    );
    const actions = page.locator(
      "[data-testid='quiz-exhaustion-actions'] button",
    );
    await expect(actions).toHaveCount(2);
    await expect(page.locator("[data-testid='quiz-try-again']")).toHaveText(
      "Let me try again",
    );
    await expect(page.locator("[data-testid='quiz-escape']")).toHaveText(
      "Walk me through it",
    );
    await expect(page.locator("[data-testid='quiz-escape-cost']")).toHaveText(
      "The breakdown shows the answer — this one won't count as solved.",
    );
    await expect(page.locator("[data-testid='quiz-nudge']")).toHaveCount(0);
  });

  test("ESC-3: escape absent at rungs 1-2 (pre-exhaustion)", async ({ page }) => {
    test.skip(!(await quizReady(page)), "quiz not rendered or flag OFF");
    const wrong = await reachCoachedLoop(page);
    test.skip(wrong == null, "could not reach a wrong pick in 3 items");
    await expect(page.locator("[data-testid='quiz-escape']")).toHaveCount(0);
    await page.locator("[data-testid='quiz-nudge']").click();
    await expect(page.locator("[data-testid='quiz-escape']")).toHaveCount(0);
  });

  test("MOM-5: switching wrong letter restarts that letter's ladder at rung 1", async ({
    page,
  }) => {
    test.skip(!(await quizReady(page)), "quiz not rendered or flag OFF");
    const first = await reachCoachedLoop(page);
    test.skip(first == null, "could not reach a wrong pick in 3 items");
    await page.locator("[data-testid='quiz-nudge']").click(); // 2 of 3 on L1
    const second = LETTERS.find((l) => l !== first)!;
    await page.locator(`[data-testid='choice-${second}']`).click();
    await page.locator("[data-testid='quiz-submit']").click();
    const feedback = page.locator("[data-testid='feedback-banner']");
    const counter = page.locator("[data-testid='quiz-rung-counter']");
    await Promise.race([
      feedback.waitFor({ state: "visible", timeout: 8_000 }).catch(() => {}),
      expect(counter).toHaveText("1 of 3", { timeout: 8_000 }).catch(() => {}),
    ]);
    test.skip(await feedback.isVisible(), `letter ${second} was correct — switch untestable here`);
    await expect(counter).toHaveText("1 of 3");
    await expect(
      page.locator("[data-testid='quiz-nudge-footnote']"),
    ).toContainText(`your pick of ${second}`);
  });
});

test.describe("v3 spec — resolution moments (ESC-1 / MOM-6 / FBK-1 / FBK-2 / VOICE-2)", () => {
  test("ESC-1/FBK-1: escape → walked-through breakdown with why-tempted; chat never revealed", async ({
    page,
  }) => {
    test.skip(!(await quizReady(page)), "quiz not rendered or flag OFF");
    const wrong = await reachCoachedLoop(page);
    test.skip(wrong == null, "could not reach a wrong pick in 3 items");
    const nudge = page.locator("[data-testid='quiz-nudge']");
    await nudge.click();
    await nudge.click();
    // FR-1 pre-check: no correct-answer marking while unresolved.
    await expect(page.getByText("CORRECT ANSWER")).toHaveCount(0);
    await page.locator("[data-testid='quiz-escape']").click();
    const banner = page.locator("[data-testid='feedback-banner']");
    await expect(banner).toBeVisible({ timeout: 10_000 });
    await expect(banner).toHaveAttribute("data-banner", "walked_through");
    // V14 / T22: banner names the answer and the last pick.
    await expect(banner).toContainText(/answer appears here/i);
    await expect(banner).toContainText(new RegExp(`last pick was ${wrong}`, "i"));
    await expect(
      page.locator("[data-testid='feedback-result-label']"),
    ).toContainText(/walked through/i);
    // FBK-1: walked-through additionally surfaces why-tempted for the last wrong letter.
    await expect(page.getByText(new RegExp(`Why ${wrong} tempted`, "i"))).toBeVisible();
  });

  test("FR-15/MOM-6: coached solve confirms in place; breakdown is opt-in", async ({
    page,
  }) => {
    test.skip(!(await quizReady(page)), "quiz not rendered or flag OFF");
    const first = await reachCoachedLoop(page);
    test.skip(first == null, "could not reach a wrong pick in 3 items");
    for (const letter of LETTERS.filter((l) => l !== first)) {
      await page.locator(`[data-testid='choice-${letter}']`).click();
      await page.locator("[data-testid='quiz-submit']").click();
      const confirm = page.locator("[data-testid='quiz-coached-confirm']");
      const coached = page.locator("[data-testid='quiz-coached-section']");
      await Promise.race([
        confirm.waitFor({ state: "visible", timeout: 8_000 }).catch(() => {}),
        coached.waitFor({ state: "visible", timeout: 8_000 }).catch(() => {}),
      ]);
      if (await confirm.isVisible()) break;
    }
    const confirm = page.locator("[data-testid='quiz-coached-confirm']");
    test.skip((await confirm.count()) === 0, "never hit the correct letter");
    // FR-15: no auto feedback; confirmation + opt-in breakdown.
    await expect(page.locator("[data-testid='feedback-banner']")).toHaveCount(0);
    await expect(
      page.locator("[data-testid='quiz-coached-confirm-label']"),
    ).toContainText("Worked through it with the coach");
    await page.locator("[data-testid='quiz-see-breakdown']").click();
    await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
      timeout: 10_000,
    });
    await expect(
      page.locator("[data-testid='feedback-result-label']"),
    ).toContainText("Worked through it with the coach");
  });

  test("FBK-2: feedback view offers the optional self-explanation input", async ({
    page,
  }) => {
    // v3 FBK-1/FBK-2: "a self-explanation input ('Saying it back makes it stick')".
    test.skip(!(await quizReady(page)), "quiz not rendered or flag OFF");
    const wrong = await reachCoachedLoop(page);
    test.skip(wrong == null, "could not reach a wrong pick in 3 items");
    const nudge = page.locator("[data-testid='quiz-nudge']");
    await nudge.click();
    await nudge.click();
    await page.locator("[data-testid='quiz-escape']").click();
    await expect(
      page.locator("[data-testid='feedback-banner']"),
    ).toBeVisible({ timeout: 10_000 });
    const selfExplain = page.locator(
      "[data-testid='feedback-self-explanation'], textarea[placeholder*='back' i]",
    );
    await expect(selfExplain.first()).toBeVisible({ timeout: 3_000 });
  });
});

test.describe("v3 spec — sequencing & summary (SEQ-2 / SUM-1)", () => {
  test("SEQ-2: item shows a labeled purpose card (V11)", async ({ page }) => {
    test.skip(!(await quizReady(page)), "quiz not rendered or flag OFF");
    const why = page.locator(
      "[data-testid='quiz-why-item'], [data-testid='quiz-why-this-item']",
    );
    await expect(why.first()).toBeVisible({ timeout: 3_000 });
    await expect(
      page.locator("[data-testid='quiz-why-item-eyebrow']"),
    ).toContainText(/picked on purpose/i);
    await expect(
      page.locator("[data-testid='quiz-why-item-body']"),
    ).toContainText(/Opening/i);
  });

  test("SUM-1: summary shows first-try-only score and honest outcome counts", async ({
    page,
  }) => {
    test.skip(!(await quizReady(page)), "quiz not rendered or flag OFF");
    // Walk one item through the priced escape so walked_through > 0.
    const wrong = await reachCoachedLoop(page);
    test.skip(wrong == null, "could not reach a wrong pick in 3 items");
    const nudge = page.locator("[data-testid='quiz-nudge']");
    await nudge.click();
    await nudge.click();
    await page.locator("[data-testid='quiz-escape']").click();
    await expect(
      page.locator("[data-testid='feedback-banner']"),
    ).toBeVisible({ timeout: 10_000 });
    // End the session from the next item and read the summary.
    await page.locator("[data-testid='quiz-next']").click();
    await page.locator("[data-testid='quiz-end-session']").click();
    const outcomes = page.locator("[data-testid='summary-outcomes']");
    await expect(outcomes).toBeVisible({ timeout: 10_000 });
    await expect(
      page.locator("[data-testid='summary-outcome-walked-through']"),
    ).toContainText(/1/);
    // SUM-1: the walked-through item must NOT be presented as solved.
    const score = page.locator("[data-testid='summary-score']");
    await expect(score).toBeVisible();
    const scoreText = (await score.textContent()) ?? "";
    const [correct] = scoreText.match(/\d+/g) ?? ["0"];
    expect(Number(correct)).toBe(0);
  });
});
