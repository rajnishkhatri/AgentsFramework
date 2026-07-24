/**
 * FR-A8 persist-error banner + FR-G3 empty-content state (L1 jsdom).
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  QuizNoContentState,
  QuizPersistErrorBanner,
} from "./QuizDurableStates";

describe("QuizNoContentState — FR-G3", () => {
  it("renders an explicit no-content status (not a danger crash)", () => {
    const html = renderToStaticMarkup(<QuizNoContentState />);
    const doc = new JSDOM(html).window.document;
    const el = doc.querySelector('[data-testid="quiz-no-content"]');
    expect(el?.getAttribute("role")).toBe("status");
    expect(el?.textContent).toMatch(/No content available/i);
  });
});

describe("QuizPersistErrorBanner — FR-A8", () => {
  it("exposes alert + retry control", () => {
    const html = renderToStaticMarkup(
      <QuizPersistErrorBanner message="Save failed" onRetry={() => {}} />,
    );
    const doc = new JSDOM(html).window.document;
    const banner = doc.querySelector('[data-testid="quiz-persist-error"]');
    expect(banner?.getAttribute("role")).toBe("alert");
    expect(banner?.textContent).toMatch(/Save failed/);
    expect(
      doc.querySelector('[data-testid="quiz-persist-retry"]'),
    ).not.toBeNull();
  });

  it("shows Saving… while retrying", () => {
    const html = renderToStaticMarkup(
      <QuizPersistErrorBanner
        message="Save failed"
        onRetry={() => {}}
        retrying
      />,
    );
    const doc = new JSDOM(html).window.document;
    const btn = doc.querySelector('[data-testid="quiz-persist-retry"]');
    expect(btn?.textContent).toMatch(/Saving/);
    expect(btn?.hasAttribute("disabled")).toBe(true);
  });
});
