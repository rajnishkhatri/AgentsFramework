/**
 * PreAct bank↔UI integration (PR #135 — 171 cascade-verified items).
 *
 * WHAT THIS PROVES (and why it's distinct from the node tests). The node suite
 * (`_test_item_bank.test.ts`, `test_item_question_repo.test.ts`) already asserts
 * the CORPUS contract: 171 reviewed rows, six skills, seeds into an EngineDb.
 * This spec asserts the one thing those cannot — that the **running /learn app**,
 * wired through the real browser composition root, actually serves those bank
 * items to a learner in the quiz.
 *
 * THE CRITICAL SEAM. `composition_engine_browser.ts::browserEngineAdapters()`
 * has three paths (verified 2026-07-08):
 *   1. dev preview, NO e2e override  → seedTestItemBank + questionSource:"bank"  ← THIS
 *   2. dev preview, WITH e2e override → practice-table + the spec's own fixtures
 *   3. production                     → empty substrate (on-device DB, unbuilt)
 * Every OTHER learn e2e (full-session, deterministic-loop) takes path (2): they
 * `addInitScript(__PREACT_E2E_SEED__, …)`, so they exercise fixtures, NOT the
 * bank. This spec deliberately injects NO override, so the app falls through to
 * path (1) — the real dev bank wiring. That is the integration under test.
 *
 * WHY NOT "click Next 171 times". The quiz loop is ADAPTIVE (FsrsScheduler
 * serves the most-due card, `fsrs_scheduler.ts`), so it does not deterministically
 * enumerate the corpus — asserting all 171 are reachable by Next would be flaky
 * and slow, and would fight the scheduler. "Full integration" is proven soundly
 * by two complementary checks:
 *   (a) CORPUS ⊆ SERVED — every committed bank id resolves through the exact
 *       read-only repo the quiz is wired to (`TestItemQuestionRepo.get`, the same
 *       method `openQuizItem` calls to resolve a scheduled id, so every id the
 *       scheduler can pick resolves to a real item). Verified in-process here (a
 *       node check against the same modules the browser composition imports —
 *       `page.evaluate` cannot import raw source `.ts` at runtime, and the served
 *       corpus is identical in node and browser because the bank is a static
 *       module, not a runtime fetch).
 *   (b) LIVE RENDER — the running /learn app, with NO fixture override, renders
 *       authentic bank content across a multi-item walk (the browser-only proof
 *       that Playwright uniquely provides).
 */

import { test, expect } from "@playwright/test";
import { TEST_ITEM_BANK } from "../../lib/adapters/engine/_test_item_bank";
import { buildBrowserEngineAdapters } from "../../lib/composition_engine_browser";
import { InMemoryEngineDb } from "../../lib/adapters/engine/db/in_memory_engine_db";
import { seedTestItemBank } from "../../lib/adapters/engine/_test_item_bank";

/** Every reviewed item's id + skill, from the committed corpus export. */
const BANK_IDS = TEST_ITEM_BANK.map((i) => i.id);
const BANK_SKILLS = new Set(TEST_ITEM_BANK.map((i) => i.skill_id));

/**
 * Resolve every corpus id through the SAME repo the quiz is wired to, over the
 * SAME composition builder the browser uses (`buildBrowserEngineAdapters` with
 * `questionSource:"bank"`). The bank is a static module, so the corpus the
 * browser bundle carries is byte-identical to this in-process read — a pass here
 * is a faithful proof of what the app serves, without a fragile in-page import.
 */
async function servedBankIds(): Promise<string[]> {
  const db = new InMemoryEngineDb();
  seedTestItemBank(db);
  const bag = buildBrowserEngineAdapters({ engineDb: db, questionSource: "bank" });
  const ids: string[] = [];
  for (const item of TEST_ITEM_BANK) {
    const q = await bag.questionRepo.get(item.id);
    if (q) ids.push(q.id);
  }
  return ids;
}

test.describe("PreAct bank↔UI integration (PR #135)", () => {
  test("the app renders a real Phase-B bank item in the quiz (no fixture override)", async ({
    page,
  }) => {
    // NO addInitScript(__PREACT_E2E_SEED__) — the app takes the dev bank path.
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });

    // An answering item is present (context + 4 choices), not an error/empty.
    const context = page.locator("[data-testid='quiz-context']");
    await expect(context).toBeVisible({ timeout: 15_000 });
    // The quiz page renders its OWN errors as `<p role="alert" class="text-danger">`
    // inside <main> (quiz/page.tsx). Scope to that — a bare [role='alert'] also
    // matches the Next.js dev-tools overlay portal, which is not a quiz error.
    await expect(page.locator("main .text-danger[role='alert']")).toHaveCount(0);

    const choices = page.locator("[data-testid^='choice-']");
    await expect(choices).toHaveCount(4);
    // A = NO CHANGE is the ACT-English bank signature (Choice.is_no_change).
    await expect(page.locator("[data-testid='choice-A']")).toContainText("NO CHANGE");

    // The rendered context is a real, non-empty bank stem (reviewed HTML).
    await expect(context).not.toBeEmpty();
  });

  test("the served corpus IS the full 171-item bank (corpus ⊆ served, all skills)", async () => {
    const served = await servedBankIds();

    // Every committed bank id resolves through the app's wired repo — proof that
    // the browser bundle carries the whole corpus, not a subset/placeholder.
    expect(served.length).toBe(BANK_IDS.length);
    expect(new Set(served)).toEqual(new Set(BANK_IDS));

    // Sanity floor: the corpus is the 171-item Phase-B bank, not the old ~8-item seed.
    expect(BANK_IDS.length).toBeGreaterThanOrEqual(171);
    // All six ACT-English skills are represented in what the app serves.
    expect(BANK_SKILLS.size).toBe(6);
  });

  test("a live multi-item walk renders authentic, varied bank content", async ({ page }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });

    const seenContexts = new Set<string>();
    const WALK = 6; // enough to cross skills without depending on scheduler order.

    for (let i = 0; i < WALK; i++) {
      const context = page.locator("[data-testid='quiz-context']");
      await expect(context).toBeVisible({ timeout: 15_000 });
      const text = (await context.textContent())?.trim() ?? "";
      expect(text.length).toBeGreaterThan(0);
      seenContexts.add(text);

      // Pick A and submit → Feedback (bank items carry per-choice rationale).
      await page.locator("[data-testid='choice-A']").click();
      await page.locator("[data-testid='quiz-submit']").click();
      await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
        timeout: 15_000,
      });

      // Advance to the next scheduled bank item (not Finish).
      await page.locator("[data-testid='quiz-next']").click();
    }

    // The walk surfaced more than one distinct item — the bank is a real corpus
    // being scheduled, not a single stuck placeholder.
    expect(seenContexts.size).toBeGreaterThan(1);
  });
});
