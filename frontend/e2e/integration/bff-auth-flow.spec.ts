/**
 * Tier 2 BFF integration -- auth error propagation.
 *
 * Verifies the BFF returns 401 when no session cookie is present, and that
 * a 401 from the mock middleware bubbles through.
 */

import { test, expect } from "@playwright/test";

test.describe.configure({ mode: "serial" });

test.describe("T2 BFF auth flow (binary: Does the BFF gate on auth?)", () => {
  test.skip(
    process.env.MOCK_MIDDLEWARE !== "1",
    "Skipped: MOCK_MIDDLEWARE!=1 (T2 integration tests).",
  );

  test("unauthenticated POST /api/run/stream returns 401", async ({ request }) => {
    const response = await request.post("/api/run/stream", {
      headers: { "content-type": "application/json" },
      data: {
        thread_id: "t-1",
        input: { messages: [{ role: "user", content: "hello" }] },
      },
    });

    expect(response.status()).toBe(401);
    const body = await response.json().catch(() => ({}));
    expect(body.error).toBe("unauthorized");
  });

  test("unauthenticated GET /api/threads returns 401", async ({ request }) => {
    const response = await request.get("/api/threads");
    expect(response.status()).toBe(401);
  });

  test("unauthenticated POST /api/run/cancel returns 401", async ({ request }) => {
    const response = await request.post("/api/run/cancel", {
      headers: { "content-type": "application/json" },
      data: { run_id: "r-1" },
    });
    expect(response.status()).toBe(401);
  });
});
