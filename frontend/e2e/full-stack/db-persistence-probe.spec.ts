/**
 * DB persistence probe — UNMOCKED full-stack (manual verification, not CI).
 *
 * Purpose: prove the deployed BFF actually persists a chat thread to Cloud SQL,
 * NOT to a per-instance InMemoryThreadRepo. `chat-persistence.spec.ts` mocks the
 * `/api/threads` routes and so only proves the CLIENT wiring; this spec mocks
 * NOTHING on the thread path — it sends a real chat, then reads the real
 * `GET /api/threads` JSON through the authenticated browser context and asserts
 * the new row is present AND survives a reload.
 *
 * If the `threads` table is missing or DATABASE_URL is unbound, the create POST
 * fails silently (the BFF `guard` swallows it) and this probe FAILS at the
 * "row present after send" assertion — which is exactly the signal we want.
 *
 * Run against the durable revision only (memui tag):
 *   cd frontend
 *   BASE_URL=https://memui---agent-frontend-w65nrxwkiq-uc.a.run.app \
 *   E2E_AUTHENTICATED=1 \
 *   pnpm exec playwright test e2e/full-stack/db-persistence-probe.spec.ts --project=chromium
 */

import { test, expect } from "@playwright/test";
import { sendMessage, composer, waitForResponse } from "../fixtures/helpers";

type ThreadRow = {
  thread_id: string;
  title: string;
  updated_at?: string;
};

async function listThreads(
  request: import("@playwright/test").APIRequestContext,
  baseURL: string,
): Promise<ThreadRow[]> {
  const res = await request.get(`${baseURL}/api/threads`);
  expect(res.ok(), `GET /api/threads -> ${res.status()}`).toBeTruthy();
  const body = (await res.json()) as { threads?: ThreadRow[] };
  return body.threads ?? [];
}

test.describe("DB persistence probe (unmocked)", () => {
  test("a sent chat is written to the durable store and survives reload", async ({
    page,
    request,
    baseURL,
  }) => {
    const root = baseURL ?? "";
    await page.goto("/");
    if ((await composer(page).count()) === 0) {
      test.skip(true, "chat shell not rendered (auth required)");
    }

    // Unique marker so we can find OUR row in the list regardless of history.
    const marker = `dbprobe ${Date.now()}`;
    const before = await listThreads(request, root);
    const beforeTitles = new Set(before.map((t) => t.title));

    await sendMessage(page, marker);
    await waitForResponse(page).catch(() => undefined);

    // Poll the REAL list endpoint until our new row shows up (BFF write landed).
    let created: ThreadRow | undefined;
    await expect
      .poll(
        async () => {
          const rows = await listThreads(request, root);
          created = rows.find(
            (t) => t.title === marker && !beforeTitles.has(t.title),
          );
          return Boolean(created);
        },
        { timeout: 20_000, message: "new thread row never appeared in /api/threads" },
      )
      .toBe(true);

    // Reload: the row must still be there. Per-instance in-memory storage would
    // drop it across the cold list call; a durable DB keeps it.
    await page.reload();
    const after = await listThreads(request, root);
    expect(
      after.some((t) => t.thread_id === created!.thread_id),
      "thread row did not survive reload -> not durable",
    ).toBeTruthy();
  });
});
