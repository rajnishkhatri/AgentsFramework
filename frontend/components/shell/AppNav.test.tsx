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
  it("iPhone: coming-soon Progress renders as a disabled non-link, not an <a href>", () => {
    const doc = dom(<AppNav surface="iphone" pathname={DASH} />);
    const progress = doc.querySelector('[data-screen="progress"]');
    expect(progress, "Progress control must render").not.toBeNull();
    // A coming-soon control is disabled and is NOT an anchor with a destination.
    expect(progress!.getAttribute("aria-disabled")).toBe("true");
    expect(progress!.tagName.toLowerCase()).not.toBe("a");
    expect(progress!.hasAttribute("href")).toBe(false);
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
  it("iPhone shows exactly Home / Practice / Progress (no Coach tab)", () => {
    const doc = dom(<AppNav surface="iphone" pathname={DASH} />);
    const labels = [...doc.querySelectorAll("[data-screen]")].map((el) =>
      el.textContent?.trim(),
    );
    expect(labels).toEqual(["Home", "Practice", "Progress"]);
    expect(doc.querySelector('[data-screen="coach"]')).toBeNull();
  });

  it("desktop shows Coach as a peer and marks the active screen", () => {
    const doc = dom(<AppNav surface="desktop" pathname={QUIZ} />);
    expect(doc.querySelector('[data-screen="coach"]')).not.toBeNull();
    const active = doc.querySelector('[data-active="true"]');
    expect(active?.getAttribute("data-screen")).toBe("quiz");
  });
});
