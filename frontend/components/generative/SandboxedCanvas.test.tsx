/**
 * Security tests for the generative-UI canvas (S3.8.3 / FE-AP-4 / FE-AP-12).
 *
 * The canvas is an AUTO-REJECT-guarded surface: any change that drops
 * `sandbox="allow-scripts"`, adds `allow-same-origin`, or replaces `srcDoc`
 * with `dangerouslySetInnerHTML` should be flagged in code review. These
 * tests capture the runtime invariants statically by inspecting the
 * rendered DOM.
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { SandboxedCanvas } from "./SandboxedCanvas";

function dom(html: string): Document {
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

describe("SandboxedCanvas runtime invariants [FE-AP-4 / FE-AP-12]", () => {
  it("renders an iframe with sandbox='allow-scripts' (no allow-same-origin)", () => {
    const html = renderToStaticMarkup(
      React.createElement(SandboxedCanvas, {
        srcDoc: "<p>hi</p>",
        title: "viz",
      }),
    );
    const iframe = dom(html).querySelector("iframe");
    expect(iframe).toBeTruthy();
    const sandbox = iframe!.getAttribute("sandbox");
    expect(sandbox).toBe("allow-scripts");
    expect(sandbox?.includes("allow-same-origin")).toBe(false);
  });

  it("uses srcDoc, NOT a real <script> element in the parent doc", () => {
    const html = renderToStaticMarkup(
      React.createElement(SandboxedCanvas, {
        srcDoc: "<script>alert(1)</script>",
        title: "viz",
      }),
    );
    const d = dom(html);
    const iframe = d.querySelector("iframe")!;
    // The dangerous payload lives entity-escaped inside the srcdoc attribute.
    expect(iframe.hasAttribute("srcdoc")).toBe(true);
    expect(iframe.getAttribute("srcdoc")).toContain("alert(1)");
    // Critically, the parent document has no executable <script> elements
    // (the iframe boundary -- backed by sandbox="allow-scripts" only --
    // is what isolates the agent-emitted JS from the host page).
    const allScripts = d.querySelectorAll("script");
    expect(allScripts.length).toBe(0);
  });

  it("requires a title (a11y)", () => {
    const html = renderToStaticMarkup(
      React.createElement(SandboxedCanvas, {
        srcDoc: "<p>hi</p>",
        title: "Sales chart",
      }),
    );
    const iframe = dom(html).querySelector("iframe")!;
    expect(iframe.getAttribute("title")).toBe("Sales chart");
  });
});
