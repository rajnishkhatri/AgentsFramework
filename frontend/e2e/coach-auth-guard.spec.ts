/**
 * D0 FR-1 — unauthenticated /learn/* must not paint the coach shell.
 *
 * Runs under chromium-desktop (NOT learn-e2e): learn-e2e sets E2E_BYPASS_AUTH
 * so the layout's test escape hatch skips withAuth. This spec needs a real
 * guard path — no bypass, no sealed session cookie.
 *
 * Q-C2 native-flow check: the (coach) RSC layout only wraps page routes under
 * /learn. Desktop/iOS deep-link auth lives at /api/auth/* (outside the group),
 * so ensureSignedIn cannot dead-lock the WebView callback. Structural assert
 * below; desktop-callback unit tests remain the regression net.
 */

import { test, expect } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const BYPASS = process.env.E2E_BYPASS_AUTH === "1";
const E2E_DIR = path.dirname(fileURLToPath(import.meta.url));

test.describe("D0 coach page guard (FR-1)", () => {
  test.skip(
    BYPASS,
    "E2E_BYPASS_AUTH=1 skips withAuth in (coach)/layout — cannot assert redirect",
  );

  for (const route of ["/learn", "/learn/coach"] as const) {
    test(`unauthenticated ${route} redirects to sign-in; no coach content`, async ({
      browser,
    }) => {
      // Fresh context: ignore any sealed E2E_AUTHENTICATED storageState.
      const context = await browser.newContext({ storageState: { cookies: [], origins: [] } });
      const page = await context.newPage();
      try {
        await page.goto(route, { waitUntil: "domcontentloaded" });
        // AuthKit ensureSignedIn redirects to WorkOS hosted login (or local
        // /api/auth/sign-in). Coach shell markers must be absent.
        await page.waitForURL(
          (url) =>
            url.href.includes("authkit.") ||
            url.href.includes("workos.") ||
            url.pathname.includes("/api/auth") ||
            url.pathname.includes("/sign-in") ||
            url.href.includes("sign-in"),
          { timeout: 15_000 },
        );
        await expect(page.getByTestId("today-focus")).toHaveCount(0);
        await expect(
          page.getByRole("navigation", { name: "Primary" }),
        ).toHaveCount(0);
      } finally {
        await context.close();
      }
    });
  }
});

test.describe("Q-C2 native deep-link auth is outside the (coach) guard", () => {
  test("desktop auth routes are not under app/(coach)", () => {
    const frontendRoot = path.resolve(E2E_DIR, "..");
    const desktopCallback = path.join(
      frontendRoot,
      "app/api/auth/desktop-callback/route.ts",
    );
    const authCatchAll = path.join(frontendRoot, "app/api/auth/[...workos]/route.ts");
    expect(fs.existsSync(desktopCallback), "desktop-callback route").toBe(true);
    expect(fs.existsSync(authCatchAll), "auth catch-all route").toBe(true);
    // Guard layout must not wrap /api — it lives only under (coach).
    const coachLayout = path.join(frontendRoot, "app/(coach)/layout.tsx");
    expect(fs.existsSync(coachLayout)).toBe(true);
    const src = fs.readFileSync(coachLayout, "utf8");
    expect(src).toMatch(/ensureSignedIn:\s*true/);
  });
});
