/**
 * PreAct deterministic learning loop (Dashboard → Quiz → Feedback → Summary).
 *
 * Pure T1: the whole loop runs on the browser-seeded `InMemoryEngineDb` — no
 * backend, no auth, no live LLM. A larger deterministic corpus
 * (`preact_learn_corpus.ts`) is injected via the non-prod seed-override hook
 * (`window.__PREACT_E2E_SEED__`, read by `composition_engine_browser.ts`) so the
 * walk is a real multi-item session, decoupled from the prod dev-seed.
 *
 * DETERMINISM. The spec does not predict FSRS scheduling order — it reads each
 * served item's correct answer at runtime and applies a SCRIPTED decision
 * (`SCRIPTED_WALK`: 3 correct, 2 wrong). The Summary score is therefore a
 * function of the spec's own choices (`EXPECTED_SCORE_TILE = "3/5"`), byte-stable
 * run-to-run. This is the walk the `learn-e2e` project records to video.
 */

import { test, expect, type Page } from "@playwright/test";
import {
  LEARN_SEED_CORPUS,
  LEARN_SEED_GLOBAL_KEY,
  LEARN_QUESTIONS,
  SCRIPTED_WALK,
  EXPECTED_SCORE_TILE,
} from "../fixtures/preact_learn_corpus";

/** Inject the e2e corpus before any app script runs (so the engine seeds from it). */
async function seedBrowser(page: Page): Promise<void> {
  await page.addInitScript(
    ([key, corpus]) => {
      (window as unknown as Record<string, unknown>)[key as string] = corpus;
    },
    [LEARN_SEED_GLOBAL_KEY, LEARN_SEED_CORPUS] as const,
  );
}

/**
 * Identify the currently-served question by its rendered choice LABELS (unique
 * across the corpus, unlike the A–D letters) and return its correct answer
 * letter. Returns null if no corpus question matches (the caller then defaults).
 */
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

test.describe("PreAct deterministic loop (Dashboard → Quiz → Feedback → Summary)", () => {
  test.beforeEach(async ({ page }) => {
    await seedBrowser(page);
  });

  test("dashboard renders the seeded mastery spread + today's focus", async ({ page }) => {
    await page.goto("/learn");

    const focus = page.locator("[data-testid='today-focus']");
    await expect(focus).toBeVisible();
    // Punctuation is the seeded weakest+due skill → the focus banner names it.
    await expect(focus).toContainText("Punctuation");

    // One card per bucket; the six seeded skills all render.
    await expect(page.locator("[data-testid^='bucket-']")).toHaveCount(6);
    await expect(page.locator("[data-testid='bucket-s-punc']")).toBeVisible();
  });

  test("a scripted 5-item walk ends on a byte-stable Summary score", async ({ page }) => {
    await page.goto("/learn");

    // Enter the Quiz from the focus banner CTA.
    await page.locator("[data-testid='today-focus'] a").click();
    await expect(page).toHaveURL(/\/learn\/quiz$/);

    for (let i = 0; i < SCRIPTED_WALK.length; i++) {
      const decision = SCRIPTED_WALK[i]!;

      // Wait for the answering phase (context + choices rendered).
      await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
        timeout: 10_000,
      });

      // Read the rendered choices: their letter (from data-testid) + label text.
      const choiceLoc = page.locator("[data-testid^='choice-']");
      await expect(choiceLoc.first()).toBeVisible();
      const choices = await choiceLoc.evaluateAll((els) =>
        els.map((e) => ({
          letter: (e.getAttribute("data-testid") ?? "").replace("choice-", ""),
          // The last <span> holds the choice label; fall back to full text.
          label: (e.querySelector("span:last-child")?.textContent ?? e.textContent ?? "").trim(),
        })),
      );
      const letters = choices.map((c) => c.letter).filter((l) => l.length === 1);

      // Match the served question by its unique choice labels → its answer letter.
      const answerLetter =
        correctLetterForLabels(choices.map((c) => c.label)) ?? letters[0]!;

      const chosen =
        decision === "correct" ? answerLetter : wrongLetter(answerLetter, letters);
      await page.locator(`[data-testid='choice-${chosen}']`).click();
      await page.locator("[data-testid='quiz-submit']").click();

      // Feedback (reviewing sub-state) shows a banner with a state-driven signal
      // (celebrate on a correct answer, soft otherwise) via `data-banner`.
      const banner = page.locator("[data-testid='feedback-banner']");
      await expect(banner).toBeVisible();
      const bannerState = await banner.getAttribute("data-banner");
      if (decision === "correct") {
        expect(bannerState).toBe("celebrate");
      } else {
        expect(bannerState).toBe("soft");
      }

      const last = i === SCRIPTED_WALK.length - 1;
      if (last) {
        await page.locator("[data-testid='quiz-finish']").click();
      } else {
        await page.locator("[data-testid='quiz-next']").click();
      }
    }

    // Summary: the STORED score (from sessionRepo.close) — deterministic 3/5.
    await expect(page).toHaveURL(/\/learn\/summary\?session=/);
    const score = page.locator("[data-testid='summary-score']");
    await expect(score).toBeVisible({ timeout: 10_000 });
    await expect(score).toContainText(EXPECTED_SCORE_TILE);

    // A recommended-next card is always present (never a dead control, FR-B5).
    await expect(page.locator("[data-testid='summary-recommended']")).toBeVisible();
  });
});
