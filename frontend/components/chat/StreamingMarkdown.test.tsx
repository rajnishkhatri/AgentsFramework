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

describe("StreamingMarkdown rendering (eval-UI F4)", () => {
  function render(text: string): Document {
    return dom(
      renderToStaticMarkup(React.createElement(StreamingMarkdown, { text })),
    );
  }

  it("a dangling fence mid-stream does not throw and renders a code block (failure path)", () => {
    const d = render("Working:\n```python\nprint('hi')\n");
    expect(d.querySelector("[data-testid='code-block'] code")?.textContent).toBe(
      "print('hi')",
    );
  });

  it("raw HTML in the source is NOT rendered as elements (no dangerouslySetInnerHTML)", () => {
    const d = render('hello <img src=x onerror="alert(1)"> world');
    expect(d.querySelector("img")).toBeNull();
  });

  it("renders headings and lists as real elements", () => {
    const d = render("## Section\n\n- one\n- two");
    expect(d.querySelector("h2")?.textContent).toBe("Section");
    expect(d.querySelectorAll("ul li").length).toBe(2);
  });

  it("fenced code renders with a language tag and a copy button", () => {
    const d = render("```python\nx = 1\n```");
    const block = d.querySelector("[data-testid='code-block']");
    expect(block?.textContent).toContain("python");
    expect(block?.querySelector("[data-testid='copy-code']")).toBeTruthy();
    expect(block?.querySelector("code")?.textContent).toBe("x = 1");
  });

  it("inline code renders as a mono chip", () => {
    const d = render("use `map` here");
    const code = d.querySelector("p code");
    expect(code?.textContent).toBe("map");
    expect(code?.className).toContain("font-mono");
  });

  it("GFM tables render as bordered tables", () => {
    const d = render("| a | b |\n|---|---|\n| 1 | 2 |");
    expect(d.querySelectorAll("table th").length).toBe(2);
    expect(d.querySelectorAll("table td").length).toBe(2);
  });
});
