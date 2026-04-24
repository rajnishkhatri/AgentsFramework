/**
 * JWT-in-browser-storage scan (SS3.3 / F-R5).
 *
 * Auto-reject anti-pattern: FE-AP-18 (no JWT in localStorage / sessionStorage).
 *
 * The frontend MAY store theme preferences and feature flags in localStorage;
 * this test only fails when a JWT-shaped value or a key matching `jwt|token|
 * bearer` is found inside an app-owned key.
 */

import { test, expect } from "@playwright/test";

const FORBIDDEN_KEY_PATTERNS = /jwt|token|bearer|access[_-]?token|id[_-]?token/i;
const JWT_VALUE_PATTERN = /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}/;

interface StorageEntry {
  readonly area: "localStorage" | "sessionStorage";
  readonly key: string;
  readonly value: string;
}

test.describe("Browser storage (binary: Is any JWT stored client-side?)", () => {
  test("no JWT-shaped value in localStorage or sessionStorage", async ({ page }) => {
    await page.goto("/");

    const entries: StorageEntry[] = await page.evaluate(() => {
      const out: { area: "localStorage" | "sessionStorage"; key: string; value: string }[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k !== null) out.push({ area: "localStorage", key: k, value: localStorage.getItem(k) ?? "" });
      }
      for (let i = 0; i < sessionStorage.length; i++) {
        const k = sessionStorage.key(i);
        if (k !== null) out.push({ area: "sessionStorage", key: k, value: sessionStorage.getItem(k) ?? "" });
      }
      return out;
    });

    const offenders = entries.filter(
      (e) => FORBIDDEN_KEY_PATTERNS.test(e.key) || JWT_VALUE_PATTERN.test(e.value),
    );
    expect(
      offenders,
      `Found JWT-shaped data in browser storage: ${JSON.stringify(offenders)}`,
    ).toEqual([]);
  });

  test("WorkOS session cookie is HttpOnly when present", async ({ page, context }) => {
    await page.goto("/");
    const cookies = await context.cookies();
    const workosCookies = cookies.filter((c) =>
      /workos|authkit|wos-session/i.test(c.name),
    );
    for (const c of workosCookies) {
      expect(c.httpOnly, `Cookie ${c.name} must be HttpOnly`).toBe(true);
    }
  });
});
