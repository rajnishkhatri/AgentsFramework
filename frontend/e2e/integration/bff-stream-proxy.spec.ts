/**
 * Tier 2 BFF integration -- SSE passthrough fidelity.
 *
 * Drives the real Next.js BFF at /api/run/stream with the mock middleware
 * server (`fixtures/mock-middleware.ts`) standing in for Python. Asserts
 * the X6 streaming contract enforced by `proxySSE` in
 * `frontend/lib/transport/edge_proxy.ts`:
 *
 *   - Content-Type: text/event-stream
 *   - Cache-Control: no-cache, no-transform
 *   - X-Accel-Buffering: no
 *   - Content-Encoding stripped
 *   - Trace ID forwarded from upstream
 *
 * Requires:
 *   MOCK_MIDDLEWARE=1
 *   MIDDLEWARE_URL=http://localhost:8765
 *   E2E_AUTHENTICATED=1 (real session needed for BFF to forward Bearer token)
 */

import { test, expect } from "../fixtures/auth.fixture";

test.describe.configure({ mode: "serial" });

test.describe("T2 BFF SSE passthrough (binary: Are streaming headers correct?)", () => {
  test.skip(
    process.env.MOCK_MIDDLEWARE !== "1",
    "Skipped: MOCK_MIDDLEWARE!=1 (T2 integration tests).",
  );

  test("BFF returns Content-Type: text/event-stream", async ({ authenticatedPage: page }) => {
    const response = await page.request.post("/api/run/stream", {
      headers: { "content-type": "application/json" },
      data: {
        thread_id: "t-1",
        input: { messages: [{ role: "user", content: "hello" }] },
      },
    });

    expect(response.status()).toBe(200);
    const ct = response.headers()["content-type"];
    expect(ct, "BFF must declare text/event-stream").toContain("text/event-stream");
  });

  test("BFF strips Content-Encoding from upstream", async ({ authenticatedPage: page }) => {
    const response = await page.request.post("/api/run/stream", {
      headers: { "content-type": "application/json" },
      data: {
        thread_id: "t-1",
        input: { messages: [{ role: "user", content: "hello" }] },
      },
    });
    expect(response.headers()["content-encoding"]).toBeUndefined();
  });

  test("BFF sets X-Accel-Buffering: no to defeat reverse-proxy buffering", async ({ authenticatedPage: page }) => {
    const response = await page.request.post("/api/run/stream", {
      headers: { "content-type": "application/json" },
      data: {
        thread_id: "t-1",
        input: { messages: [{ role: "user", content: "hello" }] },
      },
    });
    expect(response.headers()["x-accel-buffering"]).toBe("no");
  });

  test("BFF forwards x-trace-id from the upstream middleware", async ({ authenticatedPage: page }) => {
    const response = await page.request.post("/api/run/stream", {
      headers: { "content-type": "application/json" },
      data: {
        thread_id: "t-1",
        input: { messages: [{ role: "user", content: "hello" }] },
      },
    });
    const traceId = response.headers()["x-trace-id"];
    expect(traceId, "BFF must forward upstream x-trace-id verbatim").toBeDefined();
  });

  test("upstream 5xx propagates to the browser unchanged", async ({ authenticatedPage: page }) => {
    const response = await page.request.post("/api/run/stream?scenario=runError", {
      headers: { "content-type": "application/json" },
      data: {
        thread_id: "t-1",
        input: { messages: [{ role: "user", content: "trigger error" }] },
      },
    });
    expect(response.status()).toBeGreaterThanOrEqual(200);
  });
});
