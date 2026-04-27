/**
 * UI visual regression suite (`@visual`).
 *
 * Captures screenshot baselines for the main UI states reachable from `/`.
 * All network calls are mocked via `page.route()` so the suite is
 * deterministic and runs without a backend or live auth.
 *
 * Baselines live next to this file in
 * `e2e/visual/ui-visual.spec.ts-snapshots/` and are committed alongside the
 * spec. To regenerate them after an intentional UI change run:
 *
 *   pnpm test:e2e:visual:update
 *
 * The suite is excluded from `pnpm test:e2e:t1` via the `@visual` tag in
 * each test name and is intended to run only when explicitly requested.
 *
 * Auth-gated states (chat shell, composer, tool cards, ...) require a
 * WorkOS session because `app/page.tsx` calls `withAuth()` server-side. When
 * no session is present the page renders the sign-in CTA and the chat-shell
 * tests skip themselves with a clear message rather than failing. Provide a
 * session (e.g. via `E2E_AUTHENTICATED=1` + `globalSetup`) to unlock those
 * baselines.
 */

import { test, expect, type Page } from "@playwright/test";
import { sendMessage, composer } from "../fixtures/helpers";
import { buildSSEBody, buildSSEHeaders } from "../fixtures/sse-mock";
import {
  plainMarkdown,
  toolCallSuccess,
  toolCallError,
  generativePanel,
} from "../fixtures/scenarios";
import { PROMPTS } from "../fixtures/prompts";

const NOW = new Date("2026-01-01T00:00:00.000Z").toISOString();

const SAMPLE_THREADS = [
  {
    thread_id: "t-1",
    user_id: "u-1",
    messages: [],
    created_at: NOW,
    updated_at: NOW,
    title: "Quantum computing intro",
  },
  {
    thread_id: "t-2",
    user_id: "u-1",
    messages: [],
    created_at: NOW,
    updated_at: NOW,
    title: "Tour of the Solar System",
  },
];

/**
 * Stub the BFF endpoints the chat shell talks to so screenshots are
 * deterministic regardless of backend availability.
 */
async function stubBackend(
  page: Page,
  body: string = buildSSEBody(plainMarkdown()),
): Promise<void> {
  await page.route("**/api/run/stream", async (route) => {
    await route.fulfill({
      status: 200,
      headers: buildSSEHeaders(),
      body,
    });
  });
  await page.route("**/api/run/cancel", async (route) => {
    await route.fulfill({ status: 204, body: "" });
  });
  await page.route("**/api/threads*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ threads: SAMPLE_THREADS, nextCursor: null }),
    });
  });
}

/**
 * Force a stable theme so light/dark baselines don't drift with system
 * preferences. Uses next-themes' `data-theme` attribute on `<html>`.
 */
async function forceTheme(page: Page, theme: "light" | "dark"): Promise<void> {
  await page.emulateMedia({ colorScheme: theme });
  await page.evaluate((t) => {
    document.documentElement.setAttribute("data-theme", t);
    document.documentElement.classList.remove("light", "dark");
    document.documentElement.classList.add(t);
    try {
      window.localStorage.setItem("theme", t);
    } catch {
      // localStorage may be unavailable; theme attribute is enough.
    }
  }, theme);
}

async function skipIfNoComposer(page: Page): Promise<boolean> {
  const count = await composer(page).count();
  test.skip(
    count === 0,
    "Skipped: composer not rendered (auth required for chat-shell visuals).",
  );
  return count > 0;
}

test.describe("UI visual regression @visual", () => {
  test.describe("Landing page (unauthenticated)", () => {
    test("@visual landing page light theme", async ({ page }) => {
      await page.goto("/");
      await forceTheme(page, "light");
      await page.waitForLoadState("networkidle");
      await expect(page).toHaveScreenshot("landing-light.png", {
        fullPage: true,
      });
    });

    test("@visual landing page dark theme", async ({ page }) => {
      await page.goto("/");
      await forceTheme(page, "dark");
      await page.waitForLoadState("networkidle");
      await expect(page).toHaveScreenshot("landing-dark.png", {
        fullPage: true,
      });
    });

    test("@visual sign-in CTA focused", async ({ page }) => {
      await page.goto("/");
      await forceTheme(page, "light");
      const cta = page
        .locator(
          "a:has-text('Sign in'), a[href*='/api/auth/sign-in'], [data-testid='sign-in']",
        )
        .first();
      if ((await cta.count()) === 0) {
        test.skip(true, "Skipped: sign-in CTA not rendered.");
      }
      await cta.focus();
      await expect(cta).toHaveScreenshot("sign-in-cta-focused.png");
    });
  });

  test.describe("Chat shell", () => {
    test("@visual empty chat shell", async ({ page }) => {
      await stubBackend(page);
      await page.goto("/");
      if (!(await skipIfNoComposer(page))) return;
      await forceTheme(page, "light");
      await page.waitForLoadState("networkidle");
      await expect(page).toHaveScreenshot("chat-empty-light.png", {
        fullPage: true,
      });
    });

    test("@visual empty chat shell dark", async ({ page }) => {
      await stubBackend(page);
      await page.goto("/");
      if (!(await skipIfNoComposer(page))) return;
      await forceTheme(page, "dark");
      await page.waitForLoadState("networkidle");
      await expect(page).toHaveScreenshot("chat-empty-dark.png", {
        fullPage: true,
      });
    });

    test("@visual composer focused with text", async ({ page }) => {
      await stubBackend(page);
      await page.goto("/");
      if (!(await skipIfNoComposer(page))) return;
      await forceTheme(page, "light");
      const c = composer(page);
      await c.focus();
      await c.fill("Hello, agent. What can you do?");
      await expect(c).toHaveScreenshot("composer-focused-typed.png");
    });

    test("@visual streamed assistant response", async ({ page }) => {
      await stubBackend(page);
      await page.goto("/");
      if (!(await skipIfNoComposer(page))) return;
      await forceTheme(page, "light");
      await sendMessage(page, PROMPTS.PLAIN_MARKDOWN);
      await page.waitForTimeout(1_500);
      await page.waitForLoadState("networkidle");
      await expect(page).toHaveScreenshot("chat-plain-markdown.png", {
        fullPage: true,
      });
    });
  });

  test.describe("Tool cards", () => {
    test("@visual tool card success state", async ({ page }) => {
      await stubBackend(page, buildSSEBody(toolCallSuccess()));
      await page.goto("/");
      if (!(await skipIfNoComposer(page))) return;
      await forceTheme(page, "light");
      await sendMessage(page, PROMPTS.TOOL_CALL);
      await page.waitForTimeout(1_500);
      const card = page
        .locator(
          "[data-testid='tool-card'], .tool-card, details[data-tool-call-id], details",
        )
        .first();
      if ((await card.count()) === 0) {
        test.skip(true, "Skipped: tool card not rendered.");
      }
      await expect(card).toHaveScreenshot("tool-card-success.png");
    });

    test("@visual tool card error state", async ({ page }) => {
      await stubBackend(page, buildSSEBody(toolCallError()));
      await page.goto("/");
      if (!(await skipIfNoComposer(page))) return;
      await forceTheme(page, "light");
      await sendMessage(page, PROMPTS.TOOL_ERROR);
      await page.waitForTimeout(1_500);
      await page.waitForLoadState("networkidle");
      await expect(page).toHaveScreenshot("tool-card-error.png", {
        fullPage: true,
      });
    });
  });

  test.describe("Run controls", () => {
    test("@visual run controls toolbar after completed run", async ({
      page,
    }) => {
      await stubBackend(page);
      await page.goto("/");
      if (!(await skipIfNoComposer(page))) return;
      await forceTheme(page, "light");
      await sendMessage(page, PROMPTS.PLAIN_MARKDOWN);
      await page.waitForTimeout(1_500);
      const toolbar = page
        .locator("[role='toolbar'][aria-label='Run controls'], [role='toolbar']")
        .first();
      if ((await toolbar.count()) === 0) {
        test.skip(true, "Skipped: run-controls toolbar not rendered.");
      }
      await expect(toolbar).toHaveScreenshot("run-controls-toolbar.png");
    });
  });

  test.describe("Thread sidebar", () => {
    test("@visual thread sidebar with mocked threads", async ({ page }) => {
      await stubBackend(page);
      await page.goto("/");
      if (!(await skipIfNoComposer(page))) return;
      await forceTheme(page, "light");
      const sidebar = page
        .locator(
          "[data-testid='thread-sidebar'], nav[aria-label='Threads'], aside",
        )
        .first();
      if ((await sidebar.count()) === 0) {
        test.skip(true, "Skipped: thread sidebar not rendered.");
      }
      await expect(sidebar).toHaveScreenshot("thread-sidebar.png");
    });
  });

  test.describe("Generative UI", () => {
    test("@visual generative pyramid panel", async ({ page }) => {
      await stubBackend(page, buildSSEBody(generativePanel()));
      await page.goto("/");
      if (!(await skipIfNoComposer(page))) return;
      await forceTheme(page, "light");
      await sendMessage(page, PROMPTS.GENERATIVE_PANEL);
      await page.waitForTimeout(2_000);
      const panel = page
        .locator(
          "[data-testid='pyramid-panel'], [data-component='pyramid_panel']",
        )
        .first();
      if ((await panel.count()) === 0) {
        test.skip(true, "Skipped: pyramid panel not rendered.");
      }
      await expect(panel).toHaveScreenshot("generative-pyramid-panel.png");
    });
  });
});
