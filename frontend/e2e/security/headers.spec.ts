/**
 * Security header coverage (SS3.9).
 *
 * Mirrors `frontend/middleware.ts` lines 86-93.
 */

import { test, expect } from "@playwright/test";

test.describe("Security headers (binary: Are baseline headers present?)", () => {
  test("HSTS includes preload + 2-year max-age", async ({ page }) => {
    const response = await page.goto("/");
    const hsts = response!.headers()["strict-transport-security"];
    expect(hsts).toBeDefined();
    expect(hsts).toContain("max-age=63072000");
    expect(hsts).toContain("includeSubDomains");
    expect(hsts).toContain("preload");
  });

  test("X-Content-Type-Options is nosniff", async ({ page }) => {
    const response = await page.goto("/");
    expect(response!.headers()["x-content-type-options"]).toBe("nosniff");
  });

  test("X-Frame-Options is DENY", async ({ page }) => {
    const response = await page.goto("/");
    expect(response!.headers()["x-frame-options"]).toBe("DENY");
  });

  test("Referrer-Policy is strict-origin-when-cross-origin", async ({ page }) => {
    const response = await page.goto("/");
    expect(response!.headers()["referrer-policy"]).toBe(
      "strict-origin-when-cross-origin",
    );
  });

  test("Permissions-Policy denies camera, microphone, geolocation, payment", async ({ page }) => {
    const response = await page.goto("/");
    const pp = response!.headers()["permissions-policy"]!;
    expect(pp).toBeDefined();
    expect(pp).toContain("camera=()");
    expect(pp).toContain("microphone=()");
    expect(pp).toContain("geolocation=()");
    expect(pp).toContain("payment=()");
  });
});
