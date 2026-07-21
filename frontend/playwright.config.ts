/**
 * Playwright config -- three-tier testing architecture.
 *
 * See `docs/Architectures/PLAYWRIGHT_TESTING_ARCHITECTURE.md` for the tier model:
 *
 *   T1 SSE-mocked   per-commit / PR        -- no env required
 *   T2 BFF integration nightly             -- MOCK_MIDDLEWARE=1
 *   T3 Full-stack release gate / on-demand -- E2E_AUTHENTICATED=1
 *
 * Per the Agentic Testing Pyramid (`research/tdd_agentic_systems_prompt.md`),
 * E2E tests are Layer 4 (Behavioral Validation): on-demand only, never in
 * per-commit CI for tiers requiring a real backend.
 */

import { defineConfig, devices } from "@playwright/test";
import { applyTestProfile } from "./e2e/load-profile";

// Apply the named live-testing profile (TEST_PROFILE=local|prod|stress) BEFORE
// any process.env read below, so a profile fills unset BASE_URL / E2E_* / STRESS_*
// without touching values already set explicitly on the command line. See
// e2e/testing.profiles.yml. No-op for plain `pnpm test:e2e` (the default
// profile is "local", which only sets local-safe values).
applyTestProfile();

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const MOCK_MIDDLEWARE_URL = `http://localhost:${process.env.MOCK_MIDDLEWARE_PORT ?? "8765"}`;
const USE_MOCK_MIDDLEWARE = process.env.MOCK_MIDDLEWARE === "1";
const STORAGE_STATE = process.env.E2E_STORAGE_STATE ?? "e2e/.auth/state.json";
const BYPASS_AUTH = process.env.E2E_BYPASS_AUTH === "1";

function isLocalBaseUrl(url: string): boolean {
  try {
    const host = new URL(url).hostname;
    return host === "localhost" || host === "127.0.0.1" || host === "::1";
  } catch {
    return true;
  }
}

const webServers: NonNullable<Parameters<typeof defineConfig>[0]["webServer"]> = [];

if (!process.env.CI && isLocalBaseUrl(BASE_URL)) {
  webServers.push({
    command: "npm run dev",
    url: BASE_URL,
    // When auth bypass is requested we MUST start a fresh dev server so
    // it inherits the E2E_BYPASS_AUTH env. A reused server would still
    // be enforcing real WorkOS auth.
    reuseExistingServer: !BYPASS_AUTH,
    timeout: 60_000,
    env: {
      ...(USE_MOCK_MIDDLEWARE ? { MIDDLEWARE_URL: MOCK_MIDDLEWARE_URL } : {}),
      ...(BYPASS_AUTH ? { E2E_BYPASS_AUTH: "1" } : {}),
      // C1-fix FR-2: composition-root fail-once for rail Retry e2e rows.
      NEXT_PUBLIC_PREACT_E2E_HOOKS: "1",
      // Commit-first (FR-14 / plan R2): existing learn-e2e specs assume instant
      // feedback. Default OFF for the Playwright webServer; opt in with
      // NEXT_PUBLIC_FF_COMMIT_FIRST_COACH=1 for quiz-commit-first.spec.ts.
      NEXT_PUBLIC_FF_COMMIT_FIRST_COACH:
        process.env.NEXT_PUBLIC_FF_COMMIT_FIRST_COACH ?? "0",
    },
  });
}

if (USE_MOCK_MIDDLEWARE) {
  webServers.push({
    command: "npm run mock-middleware",
    url: `${MOCK_MIDDLEWARE_URL}/healthz`,
    reuseExistingServer: true,
    timeout: 10_000,
  });
}

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "html",

  timeout: 60_000,
  expect: {
    timeout: 10_000,
    toHaveScreenshot: {
      // Visual regression defaults for the e2e/visual/ suite. Pixel-diff
      // baselines tolerate small antialiasing/font-hinting drift but still
      // catch real layout/color regressions.
      maxDiffPixelRatio: 0.02,
      threshold: 0.2,
      animations: "disabled",
      caret: "hide",
      scale: "css",
    },
  },

  ...(process.env.E2E_AUTHENTICATED === "1"
    ? { globalSetup: "./e2e/global-setup.ts" as const }
    : {}),

  use: {
    baseURL: BASE_URL,
    locale: "en-US",
    trace: "retain-on-failure",
    // E2E_SCREENSHOTS=1 captures a final-state screenshot for every test
    // (pass and fail) so smoke runs leave reviewable visual evidence;
    // pair with --output=<dir> to collect them in one place.
    screenshot: process.env.E2E_SCREENSHOTS === "1" ? "on" : "only-on-failure",
    // When E2E_AUTHENTICATED=1, every test (including the visual suite that
    // uses plain `test` from @playwright/test) inherits the sealed
    // `wos-session` cookie produced by `e2e/global-setup.ts`. The
    // `authenticatedPage` fixture continues to work because it builds its
    // own context from the same file.
    ...(process.env.E2E_AUTHENTICATED === "1"
      ? { storageState: STORAGE_STATE }
      : {}),
  },

  projects: [
    // The chat/full-stack tiers ignore e2e/learn/** — those specs run only under
    // the dedicated `learn-e2e` project (video on), so a bare `playwright test`
    // does not double-run them across every browser without video.
    {
      name: "chromium-desktop",
      testIgnore: "learn/**",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-safari",
      testIgnore: "learn/**",
      use: { ...devices["iPhone 14"] },
    },
    {
      name: "webkit-desktop",
      testIgnore: "learn/**",
      use: { ...devices["Desktop Safari"] },
    },
    {
      name: "firefox-desktop",
      testIgnore: "learn/**",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "ipad",
      testIgnore: "learn/**",
      use: { ...devices["iPad (gen 7)"] },
    },
    {
      // PreAct `/learn` e2e (deterministic loop + mocked Coach + a11y). Scoped to
      // e2e/learn/ so VIDEO RECORDING is on for these specs ONLY — the reviewable
      // artifact the loop walk produces — without slowing the chat/full-stack
      // tiers, which keep trace-on-failure and no video. These specs are pure T1
      // (seeded browser engine / mocked SSE), so they need no auth.
      name: "learn-e2e",
      testDir: "./e2e/learn",
      use: {
        ...devices["Desktop Chrome"],
        video: "on",
        // Retain the trace too so a failure is debuggable alongside the video.
        trace: "retain-on-failure",
      },
    },
  ],

  ...(webServers.length > 0 ? { webServer: webServers } : {}),
});
