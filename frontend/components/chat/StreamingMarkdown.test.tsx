/**
 * a11y / smoke tests for StreamingMarkdown (S3.8.1).
 *
 * Confirms the ARIA live region uses `polite` (FE-AP-5: NEVER `assertive`)
 * and that the model badge / step meter render when provided.
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { StreamingMarkdown } from "./StreamingMarkdown";

function dom(html: string): Document {
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

describe("StreamingMarkdown a11y", () => {
  it("uses aria-live='polite' (FE-AP-5: never assertive)", () => {
    const html = renderToStaticMarkup(
      React.createElement(StreamingMarkdown, { text: "Hello" }),
    );
    const live = dom(html).querySelector("[aria-live]");
    expect(live?.getAttribute("aria-live")).toBe("polite");
    expect(live?.getAttribute("aria-live")).not.toBe("assertive");
  });

  it("renders model badge and step meter when supplied", () => {
    const html = renderToStaticMarkup(
      React.createElement(StreamingMarkdown, {
        text: "Hi",
        modelBadge: "claude-3-5-sonnet",
        step: { count: 2, name: "tool" },
      }),
    );
    const d = dom(html);
    expect(d.querySelector("[data-testid='model-badge']")?.textContent).toContain(
      "claude-3-5-sonnet",
    );
    expect(d.querySelector("[data-testid='step-meter']")?.textContent).toContain(
      "step 2",
    );
  });
});
