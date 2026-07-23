/**
 * Engine persistence probe — UNMOCKED full-stack (manual verification, not CI).
 *
 * Companion to `scripts/probe_engine_persistence.mjs` (DB-level a–e). This
 * Playwright path proves the BFF + auth cookie path (T Z.1 d/e + T B.13):
 *   (d) answering a quiz item writes an attempt the server can list
 *   (e) a second browser context resumes the same learner's open session
 *
 * Prerequisites: durable revision with DATABASE_URL + seed applied, WorkOS auth.
 *
 *   cd frontend
 *   BASE_URL=https://<durable-frontend> \
 *   E2E_AUTHENTICATED=1 \
 *   NEXT_PUBLIC_FF_DURABLE_ENGINE=1 \
 *   pnpm exec playwright test e2e/full-stack/engine-persistence-probe.spec.ts --project=chromium
 */

import { test, expect, type Page, type Browser } from "@playwright/test";

async function quizReady(page: Page): Promise<boolean> {
  await page.goto("/learn/quiz", { waitUntil: "networkidle" });
  return (await page.locator("[data-testid='quiz-progress']").count()) > 0;
}

async function submitFirstChoice(page: Page): Promise<void> {
  for (const letter of ["A", "B", "C", "D"]) {
    const choice = page.locator(`[data-testid='choice-${letter}']`);
    if ((await choice.count()) === 0) continue;
    await choice.click();
    await page.locator("[data-testid='quiz-submit']").click();
    await Promise.race([
      page.locator("[data-testid='quiz-next']").waitFor({ timeout: 15_000 }),
      page
        .locator(`[data-testid='choice-wrong-mark-${letter}']`)
        .waitFor({ timeout: 15_000 }),
      page.locator("[data-testid='quiz-persist-error']").waitFor({ timeout: 15_000 }),
    ]).catch(() => undefined);
    return;
  }
  throw new Error("no choices available to submit");
}

test.describe("Engine persistence probe (unmocked)", () => {
  test("submit persists; second context resumes the open session (FR-A5 / FR-B4)", async ({
    browser,
    page,
    request,
    baseURL,
  }: {
    browser: Browser;
    page: Page;
    request: import("@playwright/test").APIRequestContext;
    baseURL: string | undefined;
  }) => {
    test.skip(!baseURL, "BASE_URL required");
    if (!(await quizReady(page))) {
      test.skip(true, "quiz not rendered (auth/durable_engine required)");
    }

    const before = await request.get(`${baseURL}/api/engine/session/active?subject=act-english`);
    expect(before.ok(), `active before -> ${before.status()}`).toBeTruthy();
    const beforeBody = (await before.json()) as {
      session: { id: string; current_question_id: string | null } | null;
    };

    await submitFirstChoice(page);

    // (d) attempt visible via session attempts / active tally moved
    await expect
      .poll(
        async () => {
          const res = await request.get(
            `${baseURL}/api/engine/session/active?subject=act-english`,
          );
          if (!res.ok()) return false;
          const body = (await res.json()) as {
            session: { id: string } | null;
            running_score: { score_total: number } | null;
            pointer_attempted: boolean;
          };
          return (
            body.session != null &&
            (body.pointer_attempted === true ||
              (body.running_score?.score_total ?? 0) > 0 ||
              body.session.id !== beforeBody.session?.id)
          );
        },
        { timeout: 20_000, message: "attempt never became durable on /session/active" },
      )
      .toBe(true);

    const active = await request.get(
      `${baseURL}/api/engine/session/active?subject=act-english`,
    );
    const activeBody = (await active.json()) as {
      session: { id: string; current_question_id: string | null };
      running_score: { score_correct: number; score_total: number } | null;
    };
    expect(activeBody.session?.id).toBeTruthy();

    // (e) fresh context, same auth storage → resumes same open session
    const context2 = await browser.newContext({
      storageState: await page.context().storageState(),
    });
    const page2 = await context2.newPage();
    await page2.goto("/learn/quiz", { waitUntil: "networkidle" });
    test.skip(
      (await page2.locator("[data-testid='quiz-progress']").count()) === 0,
      "second context could not open quiz",
    );

    const active2 = await context2.request.get(
      `${baseURL}/api/engine/session/active?subject=act-english`,
    );
    expect(active2.ok()).toBeTruthy();
    const body2 = (await active2.json()) as {
      session: { id: string } | null;
    };
    expect(
      body2.session?.id,
      "device-2 did not resume device-1 open session (FR-B4)",
    ).toBe(activeBody.session.id);

    await context2.close();
  });
});
