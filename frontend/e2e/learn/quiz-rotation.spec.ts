/**
 * E2E — round-robin skill rotation on the /learn quiz (S3.1, ADR-0024).
 *
 * Binary outcome: "When a learner finishes one skill's item, does the next item
 * come from a DIFFERENT skill — i.e. does the session rotate across skills rather
 * than parking on the same one (the reported 'always sentence-completion' bug)?"
 *
 * L4 Behavioral Validation (Agentic Testing Pyramid): real browser against the
 * dev-seeded bank quiz (`learn-e2e` project), on-demand only. Reads the served
 * skill from the item root's `data-skill` attribute — a stable test hook (the
 * skill is NOT visible UI until S4), so the assertion is deterministic rather
 * than inferred from prose.
 *
 * Sibling: `bank-integration.spec.ts` (proves the served corpus IS the 171-item
 * bank). This proves the ORDER that corpus is served in rotates across skills.
 *
 * Run: `npx playwright test --project=learn-e2e e2e/learn/quiz-rotation.spec.ts`
 */

import { test, expect, type Page } from "@playwright/test";

/** ≥6 walks the due skills far enough to force fall-through several times. */
const WALK = 8;

/** The served skill from the item root; "" when the quiz item is absent. */
async function currentSkill(page: Page): Promise<string> {
  const el = page.locator("[data-skill]").first();
  if ((await el.count()) === 0) return "";
  return (await el.getAttribute("data-skill")) ?? "";
}

/** Answer the current item (A → Submit) and advance past feedback to the next. */
async function answerAndAdvance(page: Page): Promise<void> {
  await page.locator("[data-testid='choice-A']").click();
  await page.locator("[data-testid='quiz-submit']").click();
  await expect(page.locator("[data-testid='feedback-banner']")).toBeVisible({
    timeout: 10_000,
  });
  await page.locator("[data-testid='quiz-next']").click();
}

test.describe("Quiz rotates across skills (S3.1 / ADR-0024)", () => {
  test("no skill is served twice in a row; the walk spreads across ≥3 skills", async ({
    page,
  }) => {
    // NO addInitScript override — the app takes the dev bank path (Garvit + 171).
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });

    const first = await currentSkill(page);
    // Behaviour test, not an environment stand-up: skip if the quiz didn't render.
    test.skip(first === "", "Skipped: quiz item not rendered (auth/env).");

    const skills: string[] = [first];
    for (let i = 1; i < WALK; i++) {
      await answerAndAdvance(page);
      await page.locator("[data-skill]").first().waitFor({ timeout: 10_000 });
      skills.push(await currentSkill(page));
    }

    // The fix: a finished skill does not immediately recur while others exist.
    for (let i = 1; i < skills.length; i++) {
      expect(
        skills[i],
        `served "${skills[i]}" twice in a row at step ${i} (walk: ${skills.join(" → ")})`,
      ).not.toBe(skills[i - 1]);
    }
    // True rotation across buckets — not parked on one skill (e.g. s-sent).
    expect(
      new Set(skills).size,
      `expected ≥3 distinct skills, saw ${[...new Set(skills)].join(", ")}`,
    ).toBeGreaterThanOrEqual(3);
  });

  test("the first item exposes a resolvable served skill (data-skill hook)", async ({
    page,
  }) => {
    await page.goto("/learn/quiz", { waitUntil: "networkidle" });
    const skill = await currentSkill(page);
    test.skip(skill === "", "Skipped: quiz item not rendered (auth/env).");
    // The hook the rotation assertion depends on must be a real skill id.
    expect(skill).toMatch(/^s-[a-z]+$/);
  });
});
