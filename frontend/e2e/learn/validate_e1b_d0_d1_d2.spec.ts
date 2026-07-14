/**
 * VALIDATION WALK — Epic E1b (D0 mastery write-path + D1 accuracyStat + D2 lesson coach seed).
 *
 * Automated mirror of `scripts/validate_e1b_d0_d1_d2_ui.md`.
 * Shipped in PR #156; re-verified against current `main` frontend (post #156/#157).
 *
 * `/learn` is on-device (InMemoryEngineDb + Garvit/`__PREACT_E2E_SEED__`). No live
 * middleware required — D0/D1/D2 assert browser engine + coach_thread_store only.
 *
 * Run:
 *   E2E_BYPASS_AUTH=1 pnpm test:e2e:e1b
 */

import { test, expect, type Page } from "@playwright/test";
import {
  LEARN_SEED_CORPUS,
  LEARN_SEED_GLOBAL_KEY,
  LEARN_QUESTIONS,
} from "../fixtures/preact_learn_corpus";

/** Garvit `_dev_seed` accuracy fixture: 9/14 on-skill → 64%; newest-first bars. */
const DEV_ACCURACY_VALUE_PCT = "64%";
const DEV_ACCURACY_BAR_COUNT = 6;
const DEV_MASTERY_FOOTNOTE = /Not your mastery estimate \(28%\) — accuracy is a different number/;

async function seedBrowser(page: Page): Promise<void> {
  await page.addInitScript(
    ([key, corpus]) => {
      (window as unknown as Record<string, unknown>)[key as string] = corpus;
    },
    [LEARN_SEED_GLOBAL_KEY, LEARN_SEED_CORPUS] as const,
  );
}

async function shot(
  page: Page,
  testInfo: import("@playwright/test").TestInfo,
  name: string,
): Promise<void> {
  const buf = await page.screenshot();
  await testInfo.attach(name, { body: buf, contentType: "image/png" });
}

function correctLetterForLabels(labels: readonly string[]): string | null {
  const set = new Set(labels.map((l) => l.trim()));
  const q = LEARN_QUESTIONS.find(
    (x) =>
      x.choices.length === set.size &&
      x.choices.every((c) => set.has(c.label.trim())),
  );
  return q?.answer_letter ?? null;
}

function wrongLetter(correct: string, letters: readonly string[]): string {
  return letters.find((l) => l !== correct) ?? correct;
}

async function readMasteryPct(page: Page, skillId: string): Promise<number> {
  const bar = page.locator(
    `[data-testid="bucket-${skillId}"] [role="progressbar"]`,
  );
  await expect(bar).toBeVisible({ timeout: 10_000 });
  const raw = await bar.getAttribute("aria-valuenow");
  const pct = Number(raw);
  expect(Number.isFinite(pct), `aria-valuenow="${raw}"`).toBe(true);
  return pct;
}

async function submitWrongOnCurrentItem(page: Page): Promise<void> {
  await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
    timeout: 15_000,
  });
  const choiceLoc = page.locator("[data-testid^='choice-']");
  await expect(choiceLoc.first()).toBeVisible();
  const choices = await choiceLoc.evaluateAll((els) =>
    els.map((e) => ({
      letter: (e.getAttribute("data-testid") ?? "").replace("choice-", ""),
      label: (
        e.querySelector("span:last-child")?.textContent ??
        e.textContent ??
        ""
      ).trim(),
    })),
  );
  const letters = choices.map((c) => c.letter).filter((l) => l.length === 1);
  const answerLetter =
    correctLetterForLabels(choices.map((c) => c.label)) ?? letters[0]!;
  const pick = wrongLetter(answerLetter, letters);
  await page.locator(`[data-testid="choice-${pick}"]`).click();
  await page.locator("[data-testid='quiz-submit']").click();
  await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
    timeout: 10_000,
  });
}

// ─── D0 — mastery from stability (ADR-0029) ─────────────────────────────────

test.describe("E1b-D0: mastery write-path (wrong answers must not raise mastery)", () => {
  test("FR-1 UI: three consecutive wrongs leave Punctuation mastery low (not ~100%)", async ({
    page,
  }, testInfo) => {
    test.setTimeout(90_000);
    const step = (n: number, msg: string) =>
      console.log(`  [E1b-D0/${n}] ${msg}`);

    await seedBrowser(page);
    await page.goto("/learn/quiz?focus=s-punc", { waitUntil: "networkidle" });
    test.skip(
      (await page.locator("[data-testid='quiz-context']").count()) === 0,
      "Skipped: quiz not rendered (auth/env).",
    );
    step(1, "focused Punctuation quiz open");

    for (let i = 0; i < 3; i++) {
      await submitWrongOnCurrentItem(page);
      step(2 + i, `wrong grade #${i + 1} recorded`);
      if (i < 2) {
        await page.locator("[data-testid='quiz-next']").click();
      }
    }

    // Soft-nav so the in-browser engine singleton keeps the post-review skill_state.
    await page.locator("[data-testid='quiz-end-session']").click();
    await expect(page).toHaveURL(/\/learn$/, { timeout: 15_000 });
    step(5, "End session → dashboard (same engine bag)");

    const after = await readMasteryPct(page, "s-punc");
    step(6, `Punctuation mastery after 3 wrongs = ${after}%`);
    // Pre-D0 bug pinned mastery ≈ 100% on every grade (retrievability@t≈0).
    expect(after, "mastery must not pin near 100% after wrongs").toBeLessThan(50);
    await shot(page, testInfo, "E1b-D0-mastery-after-wrongs");
  });
});

// ─── D1 — accuracyStat read + render ────────────────────────────────────────

test.describe("E1b-D1: accuracyStat on /learn/skill (dev seed)", () => {
  test("FR-3/4/6: returning lesson shows value + 6 bars + mastery footnote", async ({
    page,
  }, testInfo) => {
    test.setTimeout(60_000);
    const step = (n: number, msg: string) =>
      console.log(`  [E1b-D1/${n}] ${msg}`);

    // No e2e corpus override — Garvit `_dev_seed` already has ≥6 accuracy sessions.
    await page.goto("/learn/skill?skillId=s-punc&context=returning", {
      waitUntil: "networkidle",
    });
    await expect(page.locator("[data-testid='skill-detail']")).toBeVisible({
      timeout: 15_000,
    });
    step(1, "returning lesson rendered");

    const block = page.locator("[data-testid='block-accuracyStat']");
    await expect(block).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("[data-testid='accuracy-value']")).toHaveText(
      DEV_ACCURACY_VALUE_PCT,
    );
    await expect(page.locator("[data-testid='accuracy-bars']")).toBeVisible();
    await expect(page.locator("[data-testid^='accuracy-bar-']")).toHaveCount(
      DEV_ACCURACY_BAR_COUNT,
    );
    await expect(
      page.locator("[data-testid='accuracy-mastery-footnote']"),
    ).toHaveText(DEV_MASTERY_FOOTNOTE);
    step(2, `accuracyStat = ${DEV_ACCURACY_VALUE_PCT}, ${DEV_ACCURACY_BAR_COUNT} bars, footnote ok`);
    await shot(page, testInfo, "E1b-D1-accuracyStat");
  });

  test("FR-1: e2e corpus with no attempts → accuracyStat self-omits", async ({
    page,
  }) => {
    test.setTimeout(60_000);
    await seedBrowser(page);
    await page.goto("/learn/skill?skillId=s-punc&context=returning", {
      waitUntil: "networkidle",
    });
    await expect(page.locator("[data-testid='skill-detail']")).toBeVisible({
      timeout: 15_000,
    });
    // Lesson rail still has coachEntry; accuracyStat must not appear.
    await expect(page.locator("[data-testid='coach-entry-seam']")).toBeVisible({
      timeout: 10_000,
    });
    await expect(
      page.locator("[data-testid='block-accuracyStat']"),
    ).toHaveCount(0);
  });
});

// ─── D2 — skill-only coach seed (ADR-0030) ───────────────────────────────────

test.describe("E1b-D2: lesson → coach skill-only pin", () => {
  test("FR-3: Open coach from returning lesson → skill-pinned, pre_submit, no item panel", async ({
    page,
  }, testInfo) => {
    test.setTimeout(60_000);
    const step = (n: number, msg: string) =>
      console.log(`  [E1b-D2/${n}] ${msg}`);

    await seedBrowser(page);
    await page.goto("/learn/skill?skillId=s-punc&context=returning", {
      waitUntil: "networkidle",
    });
    await expect(page.locator("[data-testid='skill-detail']")).toBeVisible({
      timeout: 15_000,
    });
    const entry = page.locator("[data-testid='coach-entry-seam']");
    await expect(entry).toBeVisible({ timeout: 10_000 });
    step(1, "coachEntry seam visible");

    await entry.click();
    await expect(page).toHaveURL(/\/learn\/coach/, { timeout: 10_000 });
    await expect(page.locator("[data-testid='coach-current-item']")).toHaveCount(
      0,
    );
    await expect(page.getByText(/In-drill Socratic/i)).toBeVisible();
    await expect(page.getByText(/correct answer/i)).toHaveCount(0);
    step(2, "lesson pin: no Current item; In-drill Socratic; no answer leak");
    await shot(page, testInfo, "E1b-D2-lesson-coach");
  });

  test("FR-1: lesson Open coach overwrites a stale quiz item pin", async ({
    page,
  }, testInfo) => {
    test.setTimeout(120_000);
    const step = (n: number, msg: string) =>
      console.log(`  [E1b-D2-stale/${n}] ${msg}`);

    // Soft-nav chain so coach_thread_store (module singleton) survives:
    // skill → Drill link → quiz → Ask coach (item pin) → Back → history.back → skill → Open coach.
    await seedBrowser(page);
    await page.goto("/learn/skill?skillId=s-punc&context=returning", {
      waitUntil: "networkidle",
    });
    await expect(page.locator("[data-testid='skill-detail']")).toBeVisible({
      timeout: 15_000,
    });

    const drill = page.locator("[data-testid='block-dueChecklist'] a").first();
    test.skip(
      (await drill.count()) === 0,
      "No dueChecklist Drill link — cannot soft-nav to quiz",
    );
    await drill.click();
    await expect(page).toHaveURL(/\/learn\/quiz/, { timeout: 15_000 });
    await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
      timeout: 15_000,
    });
    step(1, "soft-nav skill → focused quiz via Drill");

    await submitWrongOnCurrentItem(page);
    const askCoach = page.locator("[data-testid='feedback-ask-coach']");
    test.skip(
      (await askCoach.count()) === 0,
      "Ask-the-coach missing (desktop only / correct path)",
    );
    await askCoach.click();
    await expect(page).toHaveURL(/\/learn\/coach/, { timeout: 10_000 });
    await expect(page.locator("[data-testid='coach-current-item']")).toBeVisible({
      timeout: 10_000,
    });
    step(2, "quiz Ask-coach left an item pin (Current item visible)");

    await page.locator("[data-testid='coach-back']").click();
    await expect(page).toHaveURL(/\/learn\/quiz/, { timeout: 10_000 });
    await page.goBack();
    await expect(page.locator("[data-testid='skill-detail']")).toBeVisible({
      timeout: 15_000,
    });
    step(3, "history.back restored the returning lesson (store intact)");

    await page.locator("[data-testid='coach-entry-seam']").click();
    await expect(page).toHaveURL(/\/learn\/coach/, { timeout: 10_000 });
    await expect(page.locator("[data-testid='coach-current-item']")).toHaveCount(
      0,
    );
    await expect(page.getByText(/In-drill Socratic/i)).toBeVisible();
    step(4, "lesson pin overwrote stale item pin");
    await shot(page, testInfo, "E1b-D2-stale-pin-overwrite");
  });
});
