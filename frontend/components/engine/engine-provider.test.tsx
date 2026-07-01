/**
 * Phase 0.4 — EngineProvider + useEngine() (FR-C3/B1, L1 deterministic, TAP-1).
 *
 * The C3 seam: the React context that injects the engine `EnginePortBag` into
 * client components, mirroring `composition_react.tsx`'s `AdapterProvider` /
 * `useAdapters()`. Components consume the context exclusively — no client file
 * names an engine adapter except `composition_engine_browser.ts` (Rule C2/C3).
 *
 * Convention: this repo has no @testing-library/react (adding it is an
 * ⚠️ Ask-first dependency), so — like app/chat-shell.test.tsx — we exercise the
 * hook through `renderToStaticMarkup` (hooks run during SSR) + a JSDOM parse of
 * the emitted HTML, rather than RTL `renderHook`.
 *
 * Failure path first (Anti-Pattern 6 avoided):
 *   1. useEngine() OUTSIDE a provider throws (the misuse a consumer hits first);
 * then the happy path:
 *   2. useEngine() INSIDE the provider returns the injected bag (proven by
 *      rendering a bag-derived marker into the DOM).
 *
 * Spec: docs/plan/preact-english-coach-ui.spec.md FR-C2/C3; ADR-0006/0010.
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { EngineProvider, useEngine } from "@/app/engine-provider";
import { buildBrowserEngineAdapters } from "@/lib/composition_engine_browser";

/** A leaf probe that reads the engine context and renders a marker from it. */
function Probe(): React.JSX.Element {
  const engine = useEngine();
  // grader is a concrete, DB-free port instance — its presence proves the bag
  // was injected and reached the leaf.
  return React.createElement(
    "span",
    { "data-testid": "engine-marker" },
    engine.grader ? "engine-ready" : "engine-missing",
  );
}

function dom(html: string): Document {
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

describe("FR-C3 engine_provider_and_useEngine", () => {
  it("useEngine() throws when called outside <EngineProvider>", () => {
    expect(() => renderToStaticMarkup(React.createElement(Probe))).toThrow(
      /EngineProvider/,
    );
  });

  it("useEngine() returns the injected bag inside <EngineProvider>", () => {
    const bag = buildBrowserEngineAdapters();
    const html = renderToStaticMarkup(
      React.createElement(EngineProvider, {
        bag,
        children: React.createElement(Probe),
      }),
    );
    const doc = dom(html);
    const marker = doc.querySelector('[data-testid="engine-marker"]');
    expect(marker?.textContent).toBe("engine-ready");
  });
});
