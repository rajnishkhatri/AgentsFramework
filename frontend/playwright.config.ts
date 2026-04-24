/**
 * Playwright config for Sprint 4 §S4.3.2 E2E smoke tests.
 *
 * Per the Agentic Testing Pyramid (research/tdd_agentic_systems_prompt.md),
 * E2E tests are Layer 4 (Behavioral Validation):
 *   - Uncertainty: HIGH
 *   - CI/CD: On-demand only. Never in CI per-commit.
 *   - Binary outcome framing: "Can the user sign in and chat? YES/NO."
 *
 * Run locally: `npx playwright test`
 * Run against staging: `BASE_URL=https://staging.example.com npx playwright test`
 */

import { defineConfig, devices } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";

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
  },

  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
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
  ],

  ...(process.env.CI
    ? {}
    : {
        webServer: {
          command: "npm run dev",
          url: BASE_URL,
          reuseExistingServer: true as const,
          timeout: 30_000,
        },
      }),
});
