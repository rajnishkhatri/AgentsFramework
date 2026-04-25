/**
 * Playwright config -- three-tier testing architecture.
 *
 * See `docs/PLAYWRIGHT_TESTING_ARCHITECTURE.md` for the tier model:
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

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const MOCK_MIDDLEWARE_URL = `http://localhost:${process.env.MOCK_MIDDLEWARE_PORT ?? "8765"}`;
const USE_MOCK_MIDDLEWARE = process.env.MOCK_MIDDLEWARE === "1";
const STORAGE_STATE = process.env.E2E_STORAGE_STATE ?? "e2e/.auth/state.json";
const BYPASS_AUTH = process.env.E2E_BYPASS_AUTH === "1";

const webServers: NonNullable<Parameters<typeof defineConfig>[0]["webServer"]> = [];

if (!process.env.CI) {
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
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
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
    {
      name: "chromium-desktop",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-safari",
      use: { ...devices["iPhone 14"] },
    },
    {
      name: "webkit-desktop",
      use: { ...devices["Desktop Safari"] },
    },
    {
      name: "firefox-desktop",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "ipad",
      use: { ...devices["iPad (gen 7)"] },
    },
  ],

  ...(webServers.length > 0 ? { webServer: webServers } : {}),
});
