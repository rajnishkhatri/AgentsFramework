/**
 * TestResultsView — SSR structural tests (L1 jsdom).
 *
 * The band logic is proven in test_scoring.test.ts; here we assert the view
 * renders the raw score + band tiles and a live back-to-dashboard control.
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { TestResultsView } from "./TestResultsView";

function dom(node: React.ReactElement): Document {
  return new JSDOM(renderToStaticMarkup(node)).window.document;
}

describe("TestResultsView", () => {
  it("renders the raw score tile", () => {
    const doc = dom(
      <TestResultsView correct={39} total={48} dashboardHref="/learn" />,
    );
    expect(doc.querySelector('[data-testid="test-score"]')!.textContent).toBe("39/48");
  });

  it("renders the official scale band tile", () => {
    const doc = dom(
      <TestResultsView correct={48} total={48} dashboardHref="/learn" />,
    );
    expect(doc.querySelector('[data-testid="test-scale-band"]')!.textContent).toBe("32–32");
  });

  it("keeps a live back-to-dashboard link (FR-B5, no dead end)", () => {
    const doc = dom(
      <TestResultsView correct={0} total={48} dashboardHref="/learn" />,
    );
    const link = doc.querySelector('[data-testid="test-back-dashboard"]')!;
    expect(link.getAttribute("href")).toBe("/learn");
  });
});
