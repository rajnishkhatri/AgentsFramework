/**
 * S5 — QuizDoneBanner SSR structural tests (FR-5, L1 jsdom).
 *
 * Repo convention: renderToStaticMarkup + JSDOM (no RTL), twin of QuizProgress.test.tsx.
 * The component is presentational (F-R1): a `targetCount` prop in, milestone text out.
 * The "reached?" decision lives in quiz_progress_vm (`complete`), not here.
 *
 * FR-5: the milestone message is REAL TEXT (not colour/icon alone), names the count,
 * and interpolates `targetCount` — never a hardcoded 30.
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QuizDoneBanner } from "./QuizDoneBanner";

function render(targetCount: number): Document {
  const html = renderToStaticMarkup(
    React.createElement(QuizDoneBanner, { targetCount }),
  );
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

describe("QuizDoneBanner — FR-5 milestone message", () => {
  it("renders the milestone as real text under a stable testid", () => {
    const doc = render(30);
    const el = doc.querySelector('[data-testid="quiz-done-banner"]');
    expect(el).not.toBeNull();
    // Real, human-readable text — not conveyed by colour/icon alone.
    expect(el?.textContent).toContain("completed");
    expect(el?.textContent).toContain("session");
  });

  it("interpolates the target count — shows the actual N, never hardcoded 30", () => {
    const doc = render(7);
    const el = doc.querySelector('[data-testid="quiz-done-banner"]');
    expect(el?.textContent).toContain("7");
    expect(el?.textContent).not.toContain("30"); // proves the count is dynamic
  });
});
