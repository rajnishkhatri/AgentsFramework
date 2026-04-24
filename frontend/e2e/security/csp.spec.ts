/**
 * CSP strict-mode security tests (SS3.1).
 *
 * Mirrors the manual checks in `docs/FRONTEND_VALIDATION.md` SS3.1 and the
 * automated checker in `frontend/scripts/check_csp_strict.ts`.
 *
 * Auto-reject anti-pattern: FE-AP-19 (CSP must not contain 'unsafe-inline'
 * or 'unsafe-eval' in production).
 */

import { test, expect } from "@playwright/test";

const isProd = process.env.NODE_ENV === "production";

test.describe("CSP (binary: Is the CSP strict?)", () => {
  test("response includes a Content-Security-Policy header", async ({ page }) => {
    const response = await page.goto("/");
    expect(response).not.toBeNull();
    const csp = response!.headers()["content-security-policy"];
    expect(csp, "CSP header must be present").toBeDefined();
  });

  test("CSP forbids 'unsafe-eval' in production builds (FE-AP-19)", async ({ page }) => {
    test.skip(!isProd, "Skipped: production-only check (set NODE_ENV=production).");
    const response = await page.goto("/");
    const csp = response!.headers()["content-security-policy"]!;
    expect(csp).not.toContain("'unsafe-eval'");
  });

  test("CSP carries a per-request nonce on script-src", async ({ page }) => {
    const response = await page.goto("/");
    const csp = response!.headers()["content-security-policy"]!;
    expect(csp).toMatch(/script-src[^;]*'nonce-[A-Za-z0-9_-]+'/);
  });

  test("CSP carries a per-request nonce on style-src", async ({ page }) => {
    const response = await page.goto("/");
    const csp = response!.headers()["content-security-policy"]!;
    expect(csp).toMatch(/style-src[^;]*'nonce-[A-Za-z0-9_-]+'/);
  });

  test("CSP sets frame-ancestors 'none' (clickjacking guard)", async ({ page }) => {
    const response = await page.goto("/");
    const csp = response!.headers()["content-security-policy"]!;
    expect(csp).toContain("frame-ancestors 'none'");
  });

  test("CSP sets object-src 'none' (plugin guard)", async ({ page }) => {
    const response = await page.goto("/");
    const csp = response!.headers()["content-security-policy"]!;
    expect(csp).toContain("object-src 'none'");
  });

  test("CSP nonces differ between requests (per-request nonce)", async ({ page }) => {
    const r1 = await page.goto("/");
    const csp1 = r1!.headers()["content-security-policy"]!;
    const r2 = await page.goto("/");
    const csp2 = r2!.headers()["content-security-policy"]!;
    const m1 = csp1.match(/'nonce-([A-Za-z0-9_-]+)'/)?.[1];
    const m2 = csp2.match(/'nonce-([A-Za-z0-9_-]+)'/)?.[1];
    expect(m1, "first nonce should be present").toBeTruthy();
    expect(m2, "second nonce should be present").toBeTruthy();
    expect(m1).not.toBe(m2);
  });
});
