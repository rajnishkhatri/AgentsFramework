/**
 * PreAct FULL-SESSION continuous walk — ONE test, ONE video.
 *
 * This is the "record the whole testing session" spec: unlike the split specs
 * (deterministic-loop / coach-mocked), everything happens inside a SINGLE
 * `test(...)` so Playwright emits exactly ONE `video.webm` covering the entire
 * journey end-to-end:
 *
 *     Dashboard  →  Quiz  →  Feedback  →  Summary  →  Coach
 *
 * Pure T1: the loop runs on the browser-seeded `InMemoryEngineDb` (the larger
 * `preact_learn_corpus.ts`, injected via the non-prod seed-override hook) and the
 * Coach turn is served from a mocked SSE route — no backend, no auth, no live LLM.
 *
 * DETERMINISM. The walk does not predict FSRS scheduling order; it reads each
 * served item's correct answer at runtime and applies a SCRIPTED decision
 * (`SCRIPTED_WALK` = 3 correct, 2 wrong), so the Summary score is a byte-stable
 * function of the spec's own choices (`EXPECTED_SCORE_TILE = "3/5"`).
 *
 * Video for this project is `video: "on"` (see the `learn-e2e` project in
 * playwright.config.ts), so this file's single test produces one continuous
 * recording of the full session.
 */

import { test, expect, type Page } from "@playwright/test";
import {
  LEARN_SEED_CORPUS,
  LEARN_SEED_GLOBAL_KEY,
  LEARN_QUESTIONS,
  SCRIPTED_WALK,
  EXPECTED_SCORE_TILE,
} from "../fixtures/preact_learn_corpus";
import { buildSSEBody, buildSSEHeaders } from "../fixtures/sse-mock";
import { coachTurn, COACH_TURN_1_TEXT } from "../fixtures/coach_transcript";

/** Inject the e2e corpus before any app script runs (so the engine seeds from it). */
async function seedBrowser(page: Page): Promise<void> {
  await page.addInitScript(
    ([key, corpus]) => {
      (window as unknown as Record<string, unknown>)[key as string] = corpus;
    },
    [LEARN_SEED_GLOBAL_KEY, LEARN_SEED_CORPUS] as const,
  );
}

/** Match the served question by its unique choice LABELS → its correct letter. */
function correctLetterForLabels(labels: readonly string[]): string | null {
  const set = new Set(labels.map((l) => l.trim()));
  const q = LEARN_QUESTIONS.find(
    (x) => x.choices.length === set.size && x.choices.every((c) => set.has(c.label.trim())),
  );
  return q?.answer_letter ?? null;
}

/** A deliberately-wrong letter: the first choice that is not the correct one. */
function wrongLetter(correct: string, letters: readonly string[]): string {
  return letters.find((l) => l !== correct) ?? correct;
}

test.describe("PreAct full session (Dashboard → Quiz → Feedback → Summary → Coach)", () => {
  test("walks the whole learning loop then a Socratic coach turn — one continuous take", async ({
    page,
  }) => {
    // The coach turn is mocked up front so the single test can flow straight
    // from Summary into a live-looking Coach exchange without a backend.
    await page.route("**/api/coach/run/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: buildSSEHeaders(),
        body: buildSSEBody(coachTurn()),
      });
    });
    await seedBrowser(page);

    // ── 1. DASHBOARD ────────────────────────────────────────────────────────
    await page.goto("/learn");

    const focus = page.locator("[data-testid='today-focus']");
    await expect(focus).toBeVisible();
    // Punctuation is the seeded weakest+due skill → the focus banner names it.
    await expect(focus).toContainText("Punctuation");
    // One card per bucket; all six seeded skills render.
    await expect(page.locator("[data-testid^='bucket-']")).toHaveCount(6);

    // ── 2. QUIZ + FEEDBACK (scripted 5-item walk) ───────────────────────────
    // Click the focus CTA (the real user path). On a cold dev server the quiz
    // route may still be compiling, so if the client-side nav lands before the
    // route is ready, fall back to a full `goto` (which waits on the server)
    // and retry until the answering phase renders.
    await page.locator("[data-testid='today-focus'] a").click();
    await expect(page).toHaveURL(/\/learn\/quiz$/);
    await expect(async () => {
      if (!(await page.locator("[data-testid='quiz-context']").isVisible())) {
        await page.goto("/learn/quiz", { waitUntil: "networkidle" });
      }
      await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
        timeout: 5_000,
      });
    }).toPass({ timeout: 30_000 });

    for (let i = 0; i < SCRIPTED_WALK.length; i++) {
      const decision = SCRIPTED_WALK[i]!;

      await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
        timeout: 10_000,
      });

      const choiceLoc = page.locator("[data-testid^='choice-']");
      await expect(choiceLoc.first()).toBeVisible();
      const choices = await choiceLoc.evaluateAll((els) =>
        els.map((e) => ({
          letter: (e.getAttribute("data-testid") ?? "").replace("choice-", ""),
          label: (e.querySelector("span:last-child")?.textContent ?? e.textContent ?? "").trim(),
        })),
      );
      const letters = choices.map((c) => c.letter).filter((l) => l.length === 1);

      const answerLetter =
        correctLetterForLabels(choices.map((c) => c.label)) ?? letters[0]!;
      const chosen =
        decision === "correct" ? answerLetter : wrongLetter(answerLetter, letters);

      await page.locator(`[data-testid='choice-${chosen}']`).click();
      await page.locator("[data-testid='quiz-submit']").click();

      // Feedback banner: celebrate on correct, soft otherwise (state-driven, not
      // color-only — the `data-banner` attribute carries the signal).
      const banner = page.locator("[data-testid='feedback-banner']");
      await expect(banner).toBeVisible();
      const bannerState = await banner.getAttribute("data-banner");
      expect(bannerState).toBe(decision === "correct" ? "celebrate" : "soft");

      const last = i === SCRIPTED_WALK.length - 1;
      await page.locator(`[data-testid='quiz-${last ? "finish" : "next"}']`).click();
    }

    // ── 3. SUMMARY (byte-stable stored score) ───────────────────────────────
    await expect(page).toHaveURL(/\/learn\/summary\?session=/);
    const score = page.locator("[data-testid='summary-score']");
    await expect(score).toBeVisible({ timeout: 10_000 });
    await expect(score).toContainText(EXPECTED_SCORE_TILE); // "3/5"
    await expect(page.locator("[data-testid='summary-recommended']")).toBeVisible();

    // ── 4. COACH (mocked Socratic SSE turn) ─────────────────────────────────
    await page.goto("/learn/coach");
    const log = page.locator("[role='log']");
    await expect(log).toBeVisible();

    const composer = page.locator("textarea").first();
    await expect(composer).toBeVisible({ timeout: 10_000 });
    await composer.fill("Why is B correct here?");
    await composer.press("Enter");

    // The streamed Socratic reply settles into the log region…
    await expect(log).toContainText("what job is that comma doing", { timeout: 10_000 });
    // …never states the answer letter…
    await expect(log).not.toContainText(/the answer is [A-D]/i);
    // …and the reassembled turn text is present.
    await expect(log).toContainText(COACH_TURN_1_TEXT.slice(0, 24));
    // The typing indicator is transient — no stuck spinner after RUN_FINISHED.
    await expect(page.locator("[data-testid='coach-typing']")).toHaveCount(0, {
      timeout: 10_000,
    });
  });
});
