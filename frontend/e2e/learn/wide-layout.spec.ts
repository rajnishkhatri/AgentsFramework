/**
 * Wide-layout CoachPanel parity — locked Direction 2b / FR matrix (ADR-0035).
 *
 * On-demand Playwright (not necessarily in `make check`). Viewports:
 * 1440×900, 1024×768, 768×1024, 390×844 + reduced-motion.
 */

import { test, expect, type Page } from "@playwright/test";
import {
  LEARN_SEED_CORPUS,
  LEARN_SEED_GLOBAL_KEY,
} from "../fixtures/preact_learn_corpus";
import { buildSSEBody, buildSSEHeaders } from "../fixtures/sse-mock";
import { coachTurn } from "../fixtures/coach_transcript";

async function seedBrowser(page: Page): Promise<void> {
  await page.addInitScript(
    ([key, corpus]) => {
      (window as unknown as Record<string, unknown>)[key as string] = corpus;
    },
    [LEARN_SEED_GLOBAL_KEY, LEARN_SEED_CORPUS] as const,
  );
}

async function mockCoachSSE(page: Page): Promise<void> {
  await page.route("**/api/coach/run/stream", async (route) => {
    await route.fulfill({
      status: 200,
      headers: buildSSEHeaders(),
      body: buildSSEBody(coachTurn()),
    });
  });
}

async function openQuiz(page: Page): Promise<void> {
  await page.goto("/learn/quiz");
  await expect(page.locator("[data-testid='quiz-context']")).toBeVisible({
    timeout: 10_000,
  });
}

test.describe("FR-10 inline desktop 1440×900", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await seedBrowser(page);
    await mockCoachSSE(page);
  });

  test("item + coach-panel-inline; Zone C nudge; ThemeToggle on 64px rail", async ({
    page,
  }) => {
    await openQuiz(page);
    await expect(page.getByTestId("coach-panel-inline")).toBeVisible();
    await expect(page.getByTestId("coach-zone-c")).toBeVisible();
    await expect(page.getByTestId("one-more-nudge")).toBeVisible();
    await expect(page.getByTestId("coach-trigger-pill")).toHaveCount(0);
    await expect(page.getByTestId("coach-edge-tab")).toHaveCount(0);

    const shell = page.getByTestId("coach-shell");
    await expect(shell).toHaveAttribute("data-sidebar", "collapsed");
    const sidebar = page.getByTestId("coach-sidebar");
    const box = await sidebar.boundingBox();
    expect(box).not.toBeNull();
    expect(Math.round(box!.width)).toBe(64);
    await expect(page.getByTestId("nav-theme-toggle")).toBeVisible();
  });

  test("FR-19: dismiss inline → panel gone; no edge-tab; thread on /learn/coach", async ({
    page,
  }) => {
    await openQuiz(page);
    await expect(page.getByTestId("coach-panel-inline")).toBeVisible();
    const composer = page
      .getByTestId("coach-panel-inline")
      .getByPlaceholder("Ask about this item…");
    await composer.fill("keep this turn");
    await composer.press("Enter");
    await expect(
      page.getByTestId("coach-panel-inline").getByRole("log"),
    ).toContainText("keep this turn");

    await page.getByTestId("coach-panel-dismiss").click();
    await expect(page.getByTestId("coach-panel-inline")).toHaveCount(0);
    await expect(page.getByTestId("coach-edge-tab")).toHaveCount(0);

    await page
      .getByRole("navigation", { name: "Primary" })
      .getByRole("link", { name: "Coach" })
      .click();
    await expect(page).toHaveURL(/\/learn\/coach$/);
    await expect(
      page.getByRole("log", { name: "Coach conversation" }),
    ).toContainText("keep this turn");
  });
});

test.describe("FR-10 inline iPad landscape 1024×768", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await seedBrowser(page);
    await mockCoachSSE(page);
  });

  test("1024−64 ≥ 900 → inline panel", async ({ page }) => {
    await openQuiz(page);
    await expect(page.getByTestId("coach-panel-inline")).toBeVisible();
    await expect(page.getByTestId("coach-trigger-pill")).toHaveCount(0);
  });

  test("FR-11: window scrollTop stays 0; Zone B / item scroll", async ({
    page,
  }) => {
    await openQuiz(page);
    await expect(page.getByTestId("coach-panel-inline")).toBeVisible();

    const afterWindowScroll = await page.evaluate(() => {
      window.scrollTo(0, 400);
      return {
        scrollY: window.scrollY,
        docTop: document.scrollingElement?.scrollTop ?? -1,
      };
    });
    expect(afterWindowScroll.scrollY).toBe(0);
    expect(afterWindowScroll.docTop).toBe(0);

    const zoneCTopBefore = await page
      .getByTestId("coach-zone-c")
      .evaluate((el) => el.getBoundingClientRect().top);

    await page.evaluate(() => {
      const zoneB = document.querySelector<HTMLElement>(
        "[data-testid='coach-zone-b']",
      );
      if (!zoneB) return;
      const spacer = document.createElement("div");
      spacer.style.height = "2400px";
      spacer.style.flexShrink = "0";
      zoneB.appendChild(spacer);
      void zoneB.offsetHeight;
      zoneB.scrollTop = 600;
    });

    const zoneCTopAfter = await page
      .getByTestId("coach-zone-c")
      .evaluate((el) => el.getBoundingClientRect().top);
    // FR-12: Zone C tops unchanged after Zone B scroll
    expect(Math.abs(zoneCTopAfter - zoneCTopBefore)).toBeLessThan(2);
  });
});

test.describe("FR-1 drawer iPad portrait 768×1024", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await seedBrowser(page);
    await mockCoachSSE(page);
  });

  test("no inline panel; pill visible; Escape closes drawer", async ({
    page,
  }) => {
    await openQuiz(page);
    await expect(page.getByTestId("coach-panel-inline")).toHaveCount(0);
    await expect(page.getByTestId("coach-trigger-pill")).toBeVisible();
    await expect(page.getByTestId("coach-edge-tab")).toHaveCount(0);

    await page.getByTestId("coach-trigger-pill").click();
    await expect(page.getByTestId("coach-drawer")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("coach-drawer")).toHaveCount(0);
    await expect(page.getByTestId("coach-trigger-pill")).toBeFocused();
  });
});

test.describe("FR-18 iPhone 390×844 negatives", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await seedBrowser(page);
    await mockCoachSSE(page);
  });

  test("no inline/drawer/pill; 4 tabs; no Skill", async ({ page }) => {
    await openQuiz(page);
    await expect(page.getByTestId("coach-panel-inline")).toHaveCount(0);
    await expect(page.getByTestId("coach-panel")).toHaveCount(0);
    await expect(page.getByTestId("coach-trigger-pill")).toHaveCount(0);
    await expect(page.getByTestId("coach-drawer")).toHaveCount(0);
    // Quiz uses FocusModeChrome — tab bar is hidden while the quiz is focused.
    await expect(page.getByTestId("focus-close")).toBeVisible();

    // FR-18 tab inventory is on non-focus iPhone chrome (Home).
    // iPhone layout does not mount `coach-shell` (sidebar shell is desktop/iPad).
    await page.goto("/learn");
    const nav = page.getByRole("navigation", { name: "Primary" });
    await expect(nav).toBeVisible({ timeout: 10_000 });
    await expect(nav).toHaveAttribute("data-surface", "iphone");
    await expect(nav.getByRole("link")).toHaveCount(4);
    await expect(nav.locator('[data-screen="skill"]')).toHaveCount(0);
  });
});

test.describe("FR-9 content remount always collapsed", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await seedBrowser(page);
    await mockCoachSSE(page);
  });

  test("Home→Quiz mounts collapsed rail (no pin restore)", async ({
    page,
  }) => {
    await page.goto("/learn");
    await expect(page.getByTestId("coach-shell")).toBeVisible({
      timeout: 10_000,
    });
    // Expand on Home (persisted).
    const toggle = page.getByTestId("sidebar-toggle");
    const shell = page.getByTestId("coach-shell");
    if ((await shell.getAttribute("data-sidebar")) === "collapsed") {
      await toggle.click();
    }
    await expect(shell).toHaveAttribute("data-sidebar", "expanded");

    await page
      .getByRole("navigation", { name: "Primary" })
      .getByRole("link", { name: "Practice" })
      .click();
    await expect(page).toHaveURL(/\/learn\/quiz/);
    await expect(page.getByTestId("coach-shell")).toHaveAttribute(
      "data-sidebar",
      "collapsed",
    );
  });
});

test.describe("Home / Progress page-scroll under h-dvh", () => {
  test("main stays overflow-y auto/scroll", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await seedBrowser(page);
    await page.goto("/learn");
    await expect(page.getByTestId("coach-shell")).toBeVisible({
      timeout: 10_000,
    });
    const homeOverflow = await page
      .getByTestId("coach-main")
      .evaluate((el) => getComputedStyle(el).overflowY);
    expect(homeOverflow).toMatch(/auto|scroll/);
  });
});

test.describe("Sidebar primary nav (FR-B1) — all destinations tappable", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await seedBrowser(page);
    await mockCoachSSE(page);
  });

  test("from Quiz, Home / Coach / Skill / Progress links navigate", async ({
    page,
  }) => {
    await openQuiz(page);
    const nav = page.getByRole("navigation", { name: "Primary" });

    await nav.getByRole("link", { name: "Home" }).click();
    await expect(page).toHaveURL(/\/learn\/?$/);

    await page.goto("/learn/quiz");
    await expect(page.getByTestId("quiz-context")).toBeVisible({
      timeout: 10_000,
    });
    await nav.getByRole("link", { name: "Coach" }).click();
    await expect(page).toHaveURL(/\/learn\/coach$/);

    await page.goto("/learn/quiz");
    await expect(page.getByTestId("quiz-context")).toBeVisible({
      timeout: 10_000,
    });
    await nav.getByRole("link", { name: "Skill" }).click();
    await expect(page).toHaveURL(/\/learn\/skill/);

    await page.goto("/learn/quiz");
    await expect(page.getByTestId("quiz-context")).toBeVisible({
      timeout: 10_000,
    });
    await nav.getByRole("link", { name: "Progress" }).click();
    await expect(page).toHaveURL(/\/learn\/progress$/);
  });

  test("drawer open does not block Home on the left rail", async ({ page }) => {
    // Mid-width → coachMode drawer; overlay must stay inside main.
    await page.setViewportSize({ width: 900, height: 800 });
    await openQuiz(page);
    await page.getByTestId("coach-trigger-pill").click();
    await expect(page.getByTestId("coach-drawer")).toBeVisible();

    await page
      .getByRole("navigation", { name: "Primary" })
      .getByRole("link", { name: "Home" })
      .click();
    await expect(page).toHaveURL(/\/learn\/?$/);
  });
});
