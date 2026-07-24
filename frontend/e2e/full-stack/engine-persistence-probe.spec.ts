/**
 * Engine persistence probe — UNMOCKED full-stack (manual verification, not CI).
 *
 * T R.6 / DoD §9: owns the authenticated FR-A5 / FR-B4 proof. The Node companion
 * `scripts/probe_engine_persistence.mjs` covers migrate + seed + FR-G2 only;
 * it no longer claims submit/resume via raw SQL.
 *
 * Proves through BFF + auth cookie (the HttpEngineDb substrate):
 *   (d) POST /api/engine/attempt writes a row listable via
 *       `POST /api/engine/db/listSessionAttempts`
 *   (e) a second browser context (shared auth storage) resumes the same
 *       learner's open session via GET /api/engine/session/active
 *
 * Prerequisites: durable revision with DATABASE_URL + seed applied, WorkOS auth
 * (`E2E_AUTHENTICATED=1`; real sign-in — `E2E_FAKE_SESSION` fails AuthKit JWKS).
 *
 *   cd frontend
 *   BASE_URL=http://localhost:3000 \
 *   E2E_AUTHENTICATED=1 \
 *   DATABASE_URL=postgres://… \
 *   NEXT_PUBLIC_FF_DURABLE_ENGINE=1 \
 *   pnpm exec playwright test e2e/full-stack/engine-persistence-probe.spec.ts \
 *     --project=chromium-desktop
 */

import { test, expect, type Browser } from "@playwright/test";
import { randomUUID } from "node:crypto";

type ActiveBody = {
  session: { id: string; current_question_id: string | null } | null;
  running_score: { score_correct: number; score_total: number } | null;
  pointer_attempted: boolean;
  complete?: boolean;
};

type NextBody = {
  empty: boolean;
  reason?: string;
  question: { id: string; subject: string } | null;
};

async function getActive(
  request: import("@playwright/test").APIRequestContext,
  baseURL: string,
): Promise<ActiveBody> {
  const res = await request.get(
    `${baseURL}/api/engine/session/active?subject=act-english`,
  );
  expect(res.ok(), `active -> ${res.status()}`).toBeTruthy();
  return (await res.json()) as ActiveBody;
}

async function listSessionAttempts(
  request: import("@playwright/test").APIRequestContext,
  baseURL: string,
  sessionId: string,
): Promise<unknown[]> {
  const res = await request.post(
    `${baseURL}/api/engine/db/listSessionAttempts`,
    {
      data: { args: [sessionId] },
      headers: { "content-type": "application/json" },
    },
  );
  expect(
    res.ok(),
    `listSessionAttempts -> ${res.status()} (BFF auth + ownership)`,
  ).toBeTruthy();
  const body = (await res.json()) as unknown;
  expect(Array.isArray(body), "listSessionAttempts must return an array").toBe(
    true,
  );
  return body as unknown[];
}

test.describe("Engine persistence probe (unmocked)", () => {
  test("submit persists; second context resumes the open session (FR-A5 / FR-B4)", async ({
    browser,
    request,
    baseURL,
  }: {
    browser: Browser;
    request: import("@playwright/test").APIRequestContext;
    baseURL: string | undefined;
  }) => {
    test.setTimeout(120_000);
    test.skip(!baseURL, "BASE_URL required");

    // Auth gate: unauthenticated → 401 (never proceed).
    const probe = await request.get(
      `${baseURL}/api/engine/session/active?subject=act-english`,
    );
    test.skip(
      probe.status() === 401,
      "not authenticated (WorkOS storage state required; E2E_FAKE_SESSION is insufficient)",
    );
    expect(probe.ok(), `active auth check -> ${probe.status()}`).toBeTruthy();

    // (d) open → next → attempt through BFF (HttpEngineDb / coarse write path)
    const openRes = await request.post(`${baseURL}/api/engine/session/open`, {
      data: {
        subject: "act-english",
        mode: "adaptive",
        target_count: 30,
      },
      headers: { "content-type": "application/json" },
    });
    expect(openRes.ok(), `session/open -> ${openRes.status()}`).toBeTruthy();
    const opened = (await openRes.json()) as { id: string };
    expect(opened.id).toBeTruthy();
    const sessionId = opened.id;

    const nextRes = await request.get(
      `${baseURL}/api/engine/next?session=${encodeURIComponent(sessionId)}`,
    );
    expect(nextRes.ok(), `next -> ${nextRes.status()}`).toBeTruthy();
    const nextBody = (await nextRes.json()) as NextBody;
    expect(nextBody.empty, "next returned empty (seed/content missing?)").toBe(
      false,
    );
    expect(nextBody.question?.id).toBeTruthy();
    const questionId = nextBody.question!.id;

    // T R.15 (a) fix: the real client (use_quiz.ts) writes the served pointer
    // via POST /session/current after /next — it is the ONLY pointer writer
    // (FR-B3a). The probe previously omitted this call, so current_question_id
    // stayed null and the pointer assertion could never pass. Mirror the client
    // here so /session/active reflects the served+attempted question.
    const currentRes = await request.post(
      `${baseURL}/api/engine/session/current`,
      {
        data: { session_id: sessionId, question_id: questionId },
        headers: { "content-type": "application/json" },
      },
    );
    expect(currentRes.ok(), `session/current -> ${currentRes.status()}`).toBeTruthy();

    const attemptRes = await request.post(`${baseURL}/api/engine/attempt`, {
      data: {
        subject: "act-english",
        session_id: sessionId,
        question_id: questionId,
        chosen_letter: "A",
        correct: true,
        elapsed_ms: 120,
        used_hint: false,
        resolution: "first_try",
        idempotency_key: randomUUID(),
      },
      headers: { "content-type": "application/json" },
    });
    expect(attemptRes.ok(), `attempt -> ${attemptRes.status()}`).toBeTruthy();
    const stored = (await attemptRes.json()) as { id: string };
    expect(stored.id).toBeTruthy();

    // Attempt must be listable — NEVER accept session-id change alone (T R.6).
    const attempts = await listSessionAttempts(request, baseURL!, sessionId);
    expect(
      attempts.length,
      "server listed zero attempts after submit (FR-A5)",
    ).toBeGreaterThan(0);

    const activeBody = await getActive(request, baseURL!);
    expect(
      activeBody.session?.id,
      "open session missing on /session/active after attempt",
    ).toBe(sessionId);
    expect(
      activeBody.pointer_attempted === true ||
        (activeBody.running_score?.score_total ?? 0) > 0,
      "active payload shows no attempt evidence (pointer_attempted / score_total)",
    ).toBe(true);

    // T R.15 (a) / FR-B3a + FR-B10: the served pointer must match the question
    // we served+attempted, and the server-computed running score must match the
    // submitted history (one first_try-correct attempt → score_correct=1,
    // score_total=1). A mismatch means the pointer write or the tally drifted.
    expect(
      activeBody.session?.current_question_id,
      "served pointer (current_question_id) must match the attempted question",
    ).toBe(questionId);
    expect(
      activeBody.running_score,
      "running_score must be present after a recorded attempt",
    ).not.toBeNull();
    expect(
      activeBody.running_score?.score_correct,
      "one first_try-correct attempt must bump score_correct to 1 (FR-B10 commit-first)",
    ).toBe(1);
    expect(
      activeBody.running_score?.score_total,
      "one resolved attempt must bump score_total to 1",
    ).toBe(1);

    // (e) fresh context, same auth storage → resumes same open session
    const context2 = await browser.newContext({
      storageState: "e2e/.auth/state.json",
    });
    const body2 = await getActive(context2.request, baseURL!);
    expect(
      body2.session?.id,
      "device-2 did not resume device-1 open session (FR-B4)",
    ).toBe(sessionId);
    // T R.15 (a): the served pointer + server running score are durable —
    // device-2 sees the SAME pointer + score device-1 wrote, proving the
    // resume position and tally are cross-device (not RAM-local).
    expect(
      body2.session?.current_question_id,
      "device-2 resume pointer must match device-1 served question (FR-B3a durable)",
    ).toBe(questionId);
    expect(
      body2.running_score?.score_correct,
      "device-2 running score_correct must match device-1 (FR-B10 durable)",
    ).toBe(1);
    expect(
      body2.running_score?.score_total,
      "device-2 running score_total must match device-1 (FR-B10 durable)",
    ).toBe(1);

    const attempts2 = await listSessionAttempts(
      context2.request,
      baseURL!,
      sessionId,
    );
    expect(attempts2.length).toBeGreaterThan(0);

    // Browser-level resume proof: loading the real Quiz page must consume the
    // durable active-session endpoint. This catches a NEXT_PUBLIC flag that is
    // present server-side but missing from the compiled client bundle.
    const page2 = await context2.newPage();
    const activeResponsePromise = page2.waitForResponse(
      (response) =>
        response.url().includes("/api/engine/session/active?") &&
        response.request().method() === "GET",
    );
    await page2.goto(`${baseURL}/learn/quiz`);
    const activeResponse = await activeResponsePromise;
    expect(activeResponse.ok(), `quiz active -> ${activeResponse.status()}`).toBe(
      true,
    );
    const uiActive = (await activeResponse.json()) as ActiveBody;
    expect(uiActive.session?.id, "Quiz page did not resume the durable session").toBe(
      sessionId,
    );
    await expect(page2.getByTestId("quiz-progress")).toContainText(
      "Question 2 of 30",
    );

    await context2.close();
  });
});
