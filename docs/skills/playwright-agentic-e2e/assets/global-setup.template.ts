/**
 * global-setup — one-time authentication, run before any test.
 *
 * Two modes, both gated by E2E_AUTHENTICATED=1:
 *   1. Fake session (E2E_FAKE_SESSION=1): mint a sealed cookie locally, no
 *      network, no real user. LOCAL targets only. Great for UI/visual tests.
 *   2. Real sign-in (default): drive the hosted login UI with test credentials.
 *
 * Either way it writes storageState to e2e/.auth/state.json (override with
 * E2E_STORAGE_STATE). Consumed by the authenticatedPage fixture.
 *
 * Adapt: COOKIE_NAME, the provider sign-in selectors, and the fake-cookie shape.
 * The fake-session path assumes an iron-session + jose sealed cookie; if your
 * app seals differently, copy the shape from its auth library's test helpers.
 */

import fs from "node:fs";
import path from "node:path";
import { chromium, type FullConfig } from "@playwright/test";
import { sealData } from "iron-session"; // only needed for the fake-session path
import { SignJWT } from "jose"; //          (remove both imports if unused)
import { CONTEXT_DEFAULTS, STORAGE_STATE_PATH } from "./fixtures/auth.fixture";

// Optionally load a repo-root .env so creds/secret are available without exporting.
function loadRootEnvFile(): void {
  const envPath = path.join(process.cwd(), "..", ".env");
  if (!fs.existsSync(envPath)) return;
  for (const raw of fs.readFileSync(envPath, "utf8").split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq <= 0) continue;
    const key = line.slice(0, eq).trim();
    if (process.env[key] !== undefined) continue;
    let val = line.slice(eq + 1).trim().replace(/\r$/, "");
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    process.env[key] = val;
  }
}
loadRootEnvFile();

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const COOKIE_NAME = process.env.SESSION_COOKIE_NAME ?? "wos-session"; // <-- adapt

/** Mint a sealed session cookie locally (LOCAL targets only). */
async function buildFakeSessionCookie(cookiePassword: string, email?: string): Promise<string> {
  const secret = new TextEncoder().encode(cookiePassword);
  const accessToken = await new SignJWT({ sid: "session_e2e", role: "member", roles: ["member"] })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("2h")
    .sign(secret);
  const user = {
    id: "user_e2e",
    email: email ?? "e2e@example.com",
    emailVerified: true,
    firstName: "E2E",
    lastName: "Tester",
    object: "user",
  };
  // Shape must match what the server expects to unseal. Copy from the auth lib.
  return sealData({ accessToken, refreshToken: "refresh_e2e", user }, { password: cookiePassword });
}

async function fakeSessionSetup(stateFile: string): Promise<void> {
  const pw = process.env.SESSION_COOKIE_PASSWORD; // <-- must match the app's secret
  if (!pw || pw.length < 32) {
    throw new Error("[setup] SESSION_COOKIE_PASSWORD missing or < 32 chars.");
  }
  const url = new URL(BASE_URL);
  const sealed = await buildFakeSessionCookie(pw, process.env.E2E_USER_EMAIL);

  const browser = await chromium.launch();
  const ctx = await browser.newContext(CONTEXT_DEFAULTS);
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
        expires: Math.floor(Date.now() / 1000) + 7200,
      },
    ]);
    await ctx.storageState({ path: stateFile });
    console.log(`[setup] Fake session '${COOKIE_NAME}' written to ${stateFile}.`);
  } finally {
    await ctx.close();
    await browser.close();
  }
}

/** Drive the hosted login UI (email + password example — adapt per provider). */
async function realSignIn(stateFile: string): Promise<void> {
  const email = process.env.E2E_USER_EMAIL;
  const password = process.env.E2E_USER_PASSWORD;
  if (!email || !password) {
    throw new Error("[setup] Set E2E_USER_EMAIL and E2E_USER_PASSWORD (from env/secret store).");
  }

  const browser = await chromium.launch();
  const ctx = await browser.newContext(CONTEXT_DEFAULTS);
  const page = await ctx.newPage();
  try {
    await page.goto(BASE_URL, { waitUntil: "domcontentloaded" });

    // Click a "Sign in" CTA if the landing page shows one.
    const cta = page.locator("button:has-text('Sign in'), a:has-text('Sign in')");
    if ((await cta.count()) > 0) await cta.first().click();

    // Wait for the hosted login, then fill it. Multiple selectors = resilient.
    await page.locator("input[type='email'], input[name='email']").first().waitFor({ timeout: 60_000 });
    await page.locator("input[type='email'], input[name='email']").first().fill(email);
    await page.locator("button[type='submit'], button:has-text('Continue')").first().click();
    await page.locator("input[type='password']").first().waitFor({ timeout: 15_000 });
    await page.locator("input[type='password']").first().fill(password);
    await page.locator("button[type='submit'], button:has-text('Sign in')").first().click();

    // Wait for the redirect BACK to the app; surface a clear error on rejection.
    try {
      await page.waitForURL((u) => u.toString().startsWith(BASE_URL), { timeout: 90_000 });
    } catch (e) {
      const body = await page.locator("body").innerText();
      if (/invalid (email|password)/i.test(body)) {
        throw new Error("[setup] Provider rejected the test credentials.");
      }
      throw e;
    }

    await ctx.storageState({ path: stateFile });
    console.log(`[setup] Saved storage state to ${stateFile}.`);
  } finally {
    await ctx.close();
    await browser.close();
  }
}

export default async function globalSetup(_config: FullConfig): Promise<void> {
  if (process.env.E2E_AUTHENTICATED !== "1") {
    console.log("[setup] E2E_AUTHENTICATED!=1 — skipping auth setup.");
    return;
  }

  const stateFile = path.isAbsolute(STORAGE_STATE_PATH)
    ? STORAGE_STATE_PATH
    : path.join(process.cwd(), STORAGE_STATE_PATH);
  fs.mkdirSync(path.dirname(stateFile), { recursive: true });

  if (process.env.E2E_REUSE_STORAGE === "1" && fs.existsSync(stateFile) && fs.statSync(stateFile).size > 0) {
    console.log(`[setup] E2E_REUSE_STORAGE=1 — reusing ${stateFile}.`);
    return;
  }

  if (process.env.E2E_FAKE_SESSION === "1") {
    await fakeSessionSetup(stateFile);
    return;
  }
  await realSignIn(stateFile);
}
