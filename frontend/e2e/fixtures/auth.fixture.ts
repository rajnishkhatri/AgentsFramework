/**
 * Authenticated-page test fixture.
 *
 * Extends `@playwright/test` with an `authenticatedPage` fixture that opens
 * a browser context using the saved storage state from `global-setup.ts`.
 * Tests that exercise authenticated paths import `test` from this module
 * instead of `@playwright/test`, then accept `{ authenticatedPage }` as a
 * fixture argument.
 *
 * Storage state path (default `e2e/.auth/state.json`) can be overridden via
 * `E2E_STORAGE_STATE`. The fixture skips the test if the file is missing
 * AND `E2E_AUTHENTICATED` is unset, so unauthenticated CI runs do not crash.
 *
 * Pairs with `global-setup.ts`, which is responsible for producing the
 * storage-state file once per test run.
 */

import fs from "node:fs";
import path from "node:path";
import { test as base, type Page } from "@playwright/test";

const DEFAULT_STORAGE_STATE = "e2e/.auth/state.json";

export const STORAGE_STATE_PATH = process.env.E2E_STORAGE_STATE ?? DEFAULT_STORAGE_STATE;

export const test = base.extend<{ authenticatedPage: Page }>({
  authenticatedPage: async ({ browser }, use, testInfo) => {
    const absolutePath = path.isAbsolute(STORAGE_STATE_PATH)
      ? STORAGE_STATE_PATH
      : path.join(process.cwd(), STORAGE_STATE_PATH);

    if (!fs.existsSync(absolutePath)) {
      testInfo.skip(
        true,
        `Skipped: storage state not found at ${absolutePath}. Run global setup or set E2E_STORAGE_STATE.`,
      );
    }

    const ctx = await browser.newContext({ storageState: absolutePath });
    const page = await ctx.newPage();
    try {
      await use(page);
    } finally {
      await ctx.close();
    }
  },
});

export { expect } from "@playwright/test";
