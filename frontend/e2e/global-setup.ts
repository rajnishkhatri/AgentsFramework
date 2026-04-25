/**
 * Playwright global setup -- one-time WorkOS sign-in.
 *
 * Runs once before any tests. Two modes:
 *
 *   1. **Fake session** (`E2E_FAKE_SESSION=1`): mints a sealed `wos-session`
 *      cookie locally using `iron-session` + `jose`, identical in shape to
 *      what `@workos-inc/authkit-nextjs` ships in its `test-helpers`. No
 *      WorkOS round-trip; no real user required. Useful for visual /
 *      component tests where we just need the chat shell to render.
 *
 *   2. **Real WorkOS sign-in** (default when `E2E_AUTHENTICATED=1`):
 *      drives the live AuthKit hosted UI with `E2E_USER_EMAIL` plus
 *      `E2E_USER_PASSWORD` or `E2E_USER_OTP`.
 *
 * Either path saves cookies/local storage to `e2e/.auth/state.json`
 * (overridable via `E2E_STORAGE_STATE`). Tests consume the state via the
 * `authenticatedPage` fixture in `fixtures/auth.fixture.ts`.
 *
 * This module never runs in plain CI: the runner exits early unless
 * `E2E_AUTHENTICATED=1`.
 *
 * Required env:
 *   E2E_AUTHENTICATED=1     -- gate flag (always required)
 *   E2E_FAKE_SESSION=1      -- opt into the local fake-session path
 *   WORKOS_COOKIE_PASSWORD  -- must match the dev server's password
 *                              (read from `.env.local` by `next dev`)
 *
 *   When NOT using fake session, also required:
 *     E2E_USER_EMAIL        -- WorkOS test user email
 *     E2E_USER_PASSWORD     -- WorkOS test user password (or)
 *     E2E_USER_OTP          -- pre-known OTP if AuthKit is in OTP mode
 *
 *   BASE_URL                -- frontend root (defaults to http://localhost:3000)
 */

import fs from "node:fs";
import path from "node:path";
import { chromium, type FullConfig } from "@playwright/test";
import { sealData } from "iron-session";
import { SignJWT } from "jose";
import { STORAGE_STATE_PATH } from "./fixtures/auth.fixture";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const COOKIE_NAME = process.env.WORKOS_COOKIE_NAME ?? "wos-session";

/**
 * Mirror of `@workos-inc/authkit-nextjs/src/test-helpers.ts::generateSession`,
 * adapted to run outside Next.js (no `cookies()`). Returns the sealed
 * cookie value, ready to attach to a Playwright context.
 */
async function buildFakeSessionCookie(opts: {
  cookiePassword: string;
  email?: string;
}): Promise<string> {
  const secret = new TextEncoder().encode(opts.cookiePassword);

  const accessToken = await new SignJWT({
    sid: "session_e2e",
    org_id: "org_e2e",
    role: "member",
    roles: ["member"],
    permissions: ["posts:create", "posts:delete"],
    entitlements: ["audit-logs"],
    feature_flags: ["device-authorization-grant"],
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setIssuer("urn:authkit:e2e")
    .setExpirationTime("2h")
    .sign(secret);

  const mockUser = {
    id: "user_e2e",
    email: opts.email ?? "e2e@example.com",
    emailVerified: true,
    profilePictureUrl: null,
    firstName: "E2E",
    lastName: "Tester",
    object: "user",
    createdAt: "2024-01-01T00:00:00Z",
    updatedAt: "2024-01-01T00:00:00Z",
    lastSignInAt: "2024-01-01T00:00:00Z",
    externalId: null,
    metadata: {},
    locale: null,
  };

  return sealData(
    { accessToken, refreshToken: "refresh_e2e", user: mockUser },
    { password: opts.cookiePassword },
  );
}

async function fakeSessionSetup(absolutePath: string): Promise<void> {
  const cookiePassword = process.env.WORKOS_COOKIE_PASSWORD;
  if (!cookiePassword) {
    throw new Error(
      "[global-setup] E2E_FAKE_SESSION=1 but WORKOS_COOKIE_PASSWORD is unset. " +
        "Source frontend/.env.local before running.",
    );
  }
  if (cookiePassword.length < 32) {
    throw new Error(
      "[global-setup] WORKOS_COOKIE_PASSWORD must be at least 32 chars (iron-session requirement).",
    );
  }

  const url = new URL(BASE_URL);
  const sealed = await buildFakeSessionCookie({
    cookiePassword,
    email: process.env.E2E_USER_EMAIL,
  });

  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  try {
    await ctx.addCookies([
      {
        name: COOKIE_NAME,
        value: sealed,
        domain: url.hostname,
        path: "/",
        httpOnly: true,
        secure: url.protocol === "https:",
        sameSite: "Lax",
        expires: Math.floor(Date.now() / 1000) + 60 * 60 * 2,
      },
    ]);
    await ctx.storageState({ path: absolutePath });
    console.log(
      `[global-setup] Fake session cookie '${COOKIE_NAME}' written to ${absolutePath}.`,
    );
  } finally {
    await ctx.close();
    await browser.close();
  }
}

export default async function globalSetup(_config: FullConfig): Promise<void> {
  if (process.env.E2E_AUTHENTICATED !== "1") {
    console.log("[global-setup] E2E_AUTHENTICATED!=1 -- skipping auth setup.");
    return;
  }

  const absolutePath = path.isAbsolute(STORAGE_STATE_PATH)
    ? STORAGE_STATE_PATH
    : path.join(process.cwd(), STORAGE_STATE_PATH);
  fs.mkdirSync(path.dirname(absolutePath), { recursive: true });

  if (process.env.E2E_FAKE_SESSION === "1") {
    await fakeSessionSetup(absolutePath);
    return;
  }

  const email = process.env.E2E_USER_EMAIL;
  const password = process.env.E2E_USER_PASSWORD;
  const otp = process.env.E2E_USER_OTP;

  if (!email || (!password && !otp)) {
    throw new Error(
      "[global-setup] E2E_AUTHENTICATED=1 but credentials missing. " +
        "Set E2E_USER_EMAIL plus one of E2E_USER_PASSWORD or E2E_USER_OTP, " +
        "or set E2E_FAKE_SESSION=1 to mint a local sealed cookie instead.",
    );
  }

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
