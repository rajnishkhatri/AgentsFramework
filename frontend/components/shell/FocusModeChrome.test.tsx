/**
 * Phase 1.1 — FocusModeChrome SSR structural tests (FR-B2, L1 jsdom).
 *
 * On iPhone focus screens (Quiz/Feedback/Coach/Summary) the bottom tab bar is
 * hidden and a "✕" close returns to the prior screen. Edge first: the close
 * affordance must be a real, reachable control with a destination (FR-B5 — never
 * a dead ✕) and the screen title must be announced.
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FocusModeChrome } from "./FocusModeChrome";
import { COACH_BASE, screen } from "./nav_model";

function dom(node: React.ReactElement): Document {
  return new JSDOM(renderToStaticMarkup(node)).window.document;
}

describe("FocusModeChrome — FR-B2 close affordance", () => {
  it('renders a "✕" close that links to the given return route (default Dashboard)', () => {
    const doc = dom(
      <FocusModeChrome screenId="quiz">
        <p>item</p>
      </FocusModeChrome>,
    );
    const close = doc.querySelector('[data-testid="focus-close"]');
    expect(close, "close control must render").not.toBeNull();
    // A real destination, not a dead control (FR-B5). Default is the coach
    // Dashboard (COACH_BASE = /learn), not the site root (chat landing).
    expect(close!.getAttribute("href")).toBe(COACH_BASE);
    // Accessible name, not a bare glyph.
    expect(close!.getAttribute("aria-label")?.toLowerCase()).toContain("close");
  });

  it("honors an explicit returnTo (prior screen), e.g. Feedback → Coach back to Feedback", () => {
    const feedbackRoute = screen("feedback").route; // /learn/feedback
    const doc = dom(
      <FocusModeChrome screenId="coach" returnTo={feedbackRoute}>
        <p>coach</p>
      </FocusModeChrome>,
    );
    expect(
      doc.querySelector('[data-testid="focus-close"]')!.getAttribute("href"),
    ).toBe(feedbackRoute);
  });

  it("announces the screen title and renders its children", () => {
    const doc = dom(
      <FocusModeChrome screenId="summary">
        <p data-testid="child">done</p>
      </FocusModeChrome>,
    );
    expect(doc.body.textContent).toContain("Summary");
    expect(doc.querySelector('[data-testid="child"]')).not.toBeNull();
  });
});
