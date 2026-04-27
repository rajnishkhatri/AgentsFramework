/**
 * Tier 2 BFF integration -- thread CRUD through real BFF route handlers.
 *
 * The thread routes use `serverPortBag().threadStore` (currently
 * `NeonFreeThreadStore` with `InMemoryThreadRepo`) -- they do NOT proxy to
 * the Python middleware. This spec exercises the real composition + handler
 * code rather than the upstream HTTP path.
 */

import { test, expect } from "../fixtures/auth.fixture";

test.describe.configure({ mode: "serial" });

test.describe("T2 BFF thread CRUD (binary: Do thread routes work end-to-end?)", () => {
  test.skip(
    process.env.MOCK_MIDDLEWARE !== "1",
    "Skipped: MOCK_MIDDLEWARE!=1 (T2 integration tests).",
  );

  test("GET /api/threads returns a list page", async ({ authenticatedPage: page }) => {
    const response = await page.request.get("/api/threads");
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty("threads");
    expect(Array.isArray(body.threads)).toBe(true);
  });

  test("POST /api/threads creates a thread and returns its state", async ({ authenticatedPage: page }) => {
    const response = await page.request.post("/api/threads", {
      headers: { "content-type": "application/json" },
      data: { user_id: "u-test", metadata: {} },
    });
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty("thread_id");
    expect(body).toHaveProperty("user_id");
    expect(body).toHaveProperty("created_at");
  });

  test("POST /api/threads with invalid body returns 400", async ({ authenticatedPage: page }) => {
    const response = await page.request.post("/api/threads", {
      headers: { "content-type": "application/json" },
      data: { not_a_user_id: true },
    });
    expect(response.status()).toBe(400);
  });

  test("POST /api/threads with no JSON body returns 400", async ({ authenticatedPage: page }) => {
    const response = await page.request.post("/api/threads", {
      headers: { "content-type": "application/json" },
      data: "not-json",
    });
    expect([400, 415]).toContain(response.status());
  });
});
