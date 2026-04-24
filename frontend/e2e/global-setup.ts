/**
 * Playwright global setup -- one-time WorkOS sign-in.
 *
 * Runs once before any tests. Performs a full WorkOS AuthKit login using
 * env credentials, then saves the resulting cookies/local storage to
 * `e2e/.auth/state.json` (overridable via `E2E_STORAGE_STATE`). Tests then
 * consume this state via the `authenticatedPage` fixture in
 * `fixtures/auth.fixture.ts`.
 *
 * This module intentionally never runs in plain CI: the runner exits early
 * unless `E2E_AUTHENTICATED=1` and the WorkOS credentials are present.
 *
 * Required env:
 *   E2E_AUTHENTICATED=1   -- gate flag
 *   E2E_USER_EMAIL        -- WorkOS test user email
 *   E2E_USER_PASSWORD     -- WorkOS test user password (or)
 *   E2E_USER_OTP          -- pre-known OTP if AuthKit is in OTP mode
 *   BASE_URL              -- frontend root (defaults to http://localhost:3000)
 */

import fs from "node:fs";
import path from "node:path";
import { chromium, type FullConfig } from "@playwright/test";
import { STORAGE_STATE_PATH } from "./fixtures/auth.fixture";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";

export default async function globalSetup(_config: FullConfig): Promise<void> {
  if (process.env.E2E_AUTHENTICATED !== "1") {
    console.log("[global-setup] E2E_AUTHENTICATED!=1 -- skipping auth setup.");
    return;
  }

  const email = process.env.E2E_USER_EMAIL;
  const password = process.env.E2E_USER_PASSWORD;
  const otp = process.env.E2E_USER_OTP;

  if (!email || (!password && !otp)) {
    throw new Error(
      "[global-setup] E2E_AUTHENTICATED=1 but credentials missing. " +
        "Set E2E_USER_EMAIL plus one of E2E_USER_PASSWORD or E2E_USER_OTP.",
    );
  }

  const absolutePath = path.isAbsolute(STORAGE_STATE_PATH)
    ? STORAGE_STATE_PATH
    : path.join(process.cwd(), STORAGE_STATE_PATH);
  fs.mkdirSync(path.dirname(absolutePath), { recursive: true });

  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  const page = await ctx.newPage();

  try {
    await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });

    const signInButton = page.locator(
      "button:has-text('Sign in'), a:has-text('Sign in')",
    );
    if ((await signInButton.count()) > 0) {
      await signInButton.first().click();
    }

    await page.waitForURL(/authkit\.|workos\./, { timeout: 30_000 });

    const emailInput = page.locator(
      "input[type='email'], input[name='email']",
    ).first();
    await emailInput.fill(email);
    await page
      .locator("button[type='submit'], button:has-text('Continue')")
      .first()
      .click();

    if (password) {
      const passwordInput = page.locator("input[type='password']").first();
      await passwordInput.waitFor({ timeout: 15_000 });
      await passwordInput.fill(password);
      await page
        .locator("button[type='submit'], button:has-text('Sign in')")
        .first()
        .click();
    } else if (otp) {
      const otpInput = page.locator(
        "input[name='code'], input[autocomplete='one-time-code']",
      ).first();
      await otpInput.waitFor({ timeout: 15_000 });
      await otpInput.fill(otp);
      await page
        .locator("button[type='submit'], button:has-text('Continue')")
        .first()
        .click();
    }

    await page.waitForURL((url) => url.toString().startsWith(BASE_URL), {
      timeout: 30_000,
    });

    await ctx.storageState({ path: absolutePath });
    console.log(`[global-setup] Saved storage state to ${absolutePath}.`);
  } finally {
    await ctx.close();
    await browser.close();
  }
}
