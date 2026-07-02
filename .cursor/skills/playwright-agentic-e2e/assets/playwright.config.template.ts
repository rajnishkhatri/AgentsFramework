/**
 * playwright.config — template for a streaming agentic chat app.
 *
 * Encodes the patterns from the skill: env-driven baseURL, a webServer that
 * only starts for LOCAL targets, auth wired behind an env gate, artifacts on
 * failure, and one project per browser/device.
 *
 * Adapt the CONFIG block, then delete this header.
 */

import { defineConfig, devices } from "@playwright/test";

// ---------------------------------------------------------------------------
// CONFIG — edit these to match the workspace.
// ---------------------------------------------------------------------------
const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000"; // local default
const STORAGE_STATE = process.env.E2E_STORAGE_STATE ?? "e2e/.auth/state.json";
const AUTHED = process.env.E2E_AUTHENTICATED === "1"; // gate: real sign-in / authed storageState
const DEV_COMMAND = "npm run dev"; // command that starts the local app
// ---------------------------------------------------------------------------

/** localhost / loopback ⇒ start a local dev server; remote ⇒ start nothing. */
function isLocalBaseUrl(url: string): boolean {
  try {
    const host = new URL(url).hostname;
    return host === "localhost" || host === "127.0.0.1" || host === "::1";
  } catch {
    return true;
  }
}

const webServers: NonNullable<
  Parameters<typeof defineConfig>[0]["webServer"]
> = [];

// Only boot a local server when the target is local AND we're not in CI against
// a deployment. A stray webServer against a remote BASE_URL will hang the run.
if (!process.env.CI && isLocalBaseUrl(BASE_URL)) {
  webServers.push({
    command: DEV_COMMAND,
    url: BASE_URL,
    reuseExistingServer: true,
    timeout: 60_000,
  });
}

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // serial is safer for a shared backend / single test user
  forbidOnly: !!process.env.CI, // fail the build if a stray test.only was committed
  retries: process.env.CI ? 1 : 0, // one retry absorbs live-model flakiness
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "html",

  timeout: 60_000, // per-test default; bump per-spec for live agents (test.setTimeout)
  expect: { timeout: 10_000 },

  // Auth wired behind the gate so unauthenticated CI never tries to sign in.
  ...(AUTHED ? { globalSetup: "./e2e/global-setup.ts" as const } : {}),

  use: {
    baseURL: BASE_URL,
    locale: "en-US", // pin locale — hosted login pages localize off Accept-Language
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    // Every test (incl. plain `test`) inherits the signed-in session when authed.
    ...(AUTHED ? { storageState: STORAGE_STATE } : {}),
  },

  projects: [
    { name: "chromium-desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "webkit-desktop", use: { ...devices["Desktop Safari"] } },
    { name: "firefox-desktop", use: { ...devices["Desktop Firefox"] } },
    { name: "mobile-safari", use: { ...devices["iPhone 14"] } },
    { name: "ipad", use: { ...devices["iPad (gen 7)"] } },
  ],

  ...(webServers.length > 0 ? { webServer: webServers } : {}),
});
