/**
 * Phase 1.1 — AppNav SSR structural tests (FR-B1/B5, L1 jsdom).
 *
 * Repo convention (no @testing-library/react): renderToStaticMarkup + JSDOM.
 * The nav MEMBERSHIP + wired/coming-soon logic is proven in nav_model.test.ts;
 * here we assert AppNav *renders that model faithfully*: enabled items are
 * real <a href> links, coming-soon items are disabled non-links (FR-B5), and the
 * active screen is marked. Edge first: the disabled control must NOT be an <a>
 * with a live href (a dead control is the failure FR-B5 forbids).
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { AppNav } from "./AppNav";
import { screen } from "./nav_model";

const DASH = screen("dashboard").route; // /learn
const QUIZ = screen("quiz").route; // /learn/quiz

function dom(node: React.ReactElement): Document {
  return new JSDOM(renderToStaticMarkup(node)).window.document;
}

describe("AppNav — FR-B5 no dead controls", () => {
  // G8-OK: Epic F ships /learn/progress — Progress is now a live link (was
  // comingSoon disabled non-link). Intended behavior change, not a weakened gate.
  it("iPhone: Progress is a live <a href=/learn/progress> (Epic F)", () => {
    const doc = dom(<AppNav surface="iphone" pathname={DASH} />);
    const progress = doc.querySelector('a[data-screen="progress"]');
    expect(progress, "Progress control must render as a link").not.toBeNull();
    expect(progress!.getAttribute("href")).toBe("/learn/progress");
    expect(progress!.getAttribute("aria-disabled")).not.toBe("true");
  });

  it("enabled items render as real links with their route as href", () => {
    const doc = dom(<AppNav surface="desktop" pathname={DASH} />);
    const home = doc.querySelector('a[data-screen="dashboard"]');
    const quiz = doc.querySelector('a[data-screen="quiz"]');
    // Routes are anchored under COACH_BASE (/learn), so they coexist with the
    // chat landing at "/" (no parallel-page collision).
    expect(home?.getAttribute("href")).toBe(DASH);
    expect(quiz?.getAttribute("href")).toBe(QUIZ);
  });
});

describe("AppNav — FR-B1 surface-appropriate membership + active state", () => {
  it("iPhone shows exactly Home / Practice / Coach / Progress (no Skill tab)", () => {
    // Mirrors nav_model NAV_MEMBERSHIP.iphone — Coach is a persistent tab;
    // Skill detail is reached via dashboard bucket→skill (not a bottom tab).
    const doc = dom(<AppNav surface="iphone" pathname={DASH} />);
    const labels = [...doc.querySelectorAll("[data-screen]")].map((el) =>
      el.textContent?.trim(),
    );
    expect(labels).toEqual(["Home", "Practice", "Coach", "Progress"]);
    expect(doc.querySelector('[data-screen="skill"]')).toBeNull();
  });

  it("desktop shows Coach as a peer and marks the active screen", () => {
    const doc = dom(<AppNav surface="desktop" pathname={QUIZ} />);
    expect(doc.querySelector('[data-screen="coach"]')).not.toBeNull();
    const active = doc.querySelector('[data-active="true"]');
    expect(active?.getAttribute("data-screen")).toBe("quiz");
  });
});

describe("AppNav — collapsed icon rail (FR-6 / B1)", () => {
  it("collapsed desktop: ≥44px full-rail hit target + lucide icon + aria-label", () => {
    const doc = dom(
      <AppNav surface="desktop" pathname={QUIZ} collapsed />,
    );
    const nav = doc.querySelector("nav");
    expect(nav?.getAttribute("data-collapsed")).toBe("true");
    const quiz = doc.querySelector('a[data-screen="quiz"]');
    expect(quiz?.getAttribute("aria-label")).toBe("Practice");
    expect(quiz?.getAttribute("title")).toBe("Practice");
    // Locked §2 / HIG: rail control is a full-width ≥44px hit target (not a
    // 38px island with dead gutters). Visual glyph stays a lucide SVG.
    expect(quiz?.className).toMatch(/min-h-11/);
    expect(quiz?.className).toMatch(/w-full/);
    expect(quiz?.querySelector("svg")).not.toBeNull();
    // Ambiguous letter fallback (two "P"s for Practice + Progress) is retired.
    expect(quiz?.textContent?.trim()).not.toBe("P");
  });

  it("every desktop rail destination is a live <a> (FR-B5 — Home/Skill/Progress too)", () => {
    const doc = dom(
      <AppNav surface="desktop" pathname={QUIZ} collapsed />,
    );
    for (const [screenId, href] of [
      ["dashboard", "/learn"],
      ["quiz", "/learn/quiz"],
      ["coach", "/learn/coach"],
      ["skill", "/learn/skill"],
      ["progress", "/learn/progress"],
    ] as const) {
      const link = doc.querySelector(`a[data-screen="${screenId}"]`);
      expect(link, `${screenId} must be a live link`).not.toBeNull();
      expect(link!.getAttribute("href")).toBe(href);
      expect(link!.getAttribute("aria-disabled")).not.toBe("true");
    }
  });

  it("FR-6: ThemeToggle is last rail item when showThemeToggle + collapsed", () => {
    const doc = dom(
      <AppNav
        surface="desktop"
        pathname={QUIZ}
        collapsed
        showThemeToggle
      />,
    );
    const theme = doc.querySelector('[data-testid="nav-theme-toggle"]');
    expect(theme).not.toBeNull();
    const children = [...doc.querySelector("nav")!.children];
    expect(children[children.length - 1]).toBe(theme);
  });

  it("showSignOut places Sign out above ThemeToggle (ThemeToggle still last)", () => {
    const doc = dom(
      <AppNav
        surface="desktop"
        pathname={QUIZ}
        collapsed
        showThemeToggle
        showSignOut
      />,
    );
    const signOut = doc.querySelector('[data-testid="nav-sign-out"]');
    const theme = doc.querySelector('[data-testid="nav-theme-toggle"]');
    expect(signOut).not.toBeNull();
    expect(
      signOut!.querySelector('[data-testid="sign-out"]')?.getAttribute("href"),
    ).toContain("/api/auth/sign-out");
    const children = [...doc.querySelector("nav")!.children];
    expect(children[children.length - 1]).toBe(theme);
    expect(children.indexOf(signOut!)).toBeLessThan(children.indexOf(theme!));
  });
});
