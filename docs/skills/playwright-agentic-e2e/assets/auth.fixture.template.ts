/**
 * auth.fixture — an `authenticatedPage` that loads the saved storageState and
 * skips gracefully when it's missing (so unauthenticated CI doesn't crash).
 *
 * Authed specs import { test, expect } from this file (NOT from
 * "@playwright/test") and accept { authenticatedPage }.
 */

import fs from "node:fs";
import path from "node:path";
import { test as base, type Page } from "@playwright/test";

// Keep these context defaults identical in global-setup so sign-in and tests
// agree on locale (prevents the hosted-login-page localization trap).
export const CONTEXT_DEFAULTS = {
  locale: "en-US" as const,
  extraHTTPHeaders: { "Accept-Language": "en-US,en;q=0.9" },
};

const DEFAULT_STORAGE_STATE = "e2e/.auth/state.json";
export const STORAGE_STATE_PATH =
  process.env.E2E_STORAGE_STATE ?? DEFAULT_STORAGE_STATE;

export const test = base.extend<{ authenticatedPage: Page }>({
  authenticatedPage: async ({ browser }, use, testInfo) => {
    const abs = path.isAbsolute(STORAGE_STATE_PATH)
      ? STORAGE_STATE_PATH
      : path.join(process.cwd(), STORAGE_STATE_PATH);

    if (!fs.existsSync(abs)) {
      testInfo.skip(
        true,
        `No storage state at ${abs}. Run global setup (E2E_AUTHENTICATED=1) or set E2E_STORAGE_STATE.`,
      );
    }

    const ctx = await browser.newContext({
      ...CONTEXT_DEFAULTS,
      storageState: abs,
    });
    const page = await ctx.newPage();
    try {
      await use(page);
    } finally {
      await ctx.close();
    }
  },
});

export { expect } from "@playwright/test";
