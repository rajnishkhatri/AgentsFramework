// B1/C3: 'use client' required — this file establishes a React context
// (createContext + useContext) that injects the engine EnginePortBag into the
// client component tree. It is the engine twin of composition_react.tsx's
// AdapterProvider/useAdapters, kept as a leaf provider so the engine bounded
// context stays separate from the chat PortBag.
"use client";

import * as React from "react";
import type { EnginePortBag } from "@/lib/composition_engine";
import { browserEngineAdapters } from "@/lib/composition_engine_browser";

const EngineContext = React.createContext<EnginePortBag | null>(null);

/**
 * Provides the engine `EnginePortBag` to the subtree. `bag` is optional: when
 * omitted, the browser-safe singleton (`browserEngineAdapters()`, InMemoryEngineDb
 * substrate — ADR-0005/0010) is used, so the root layout can mount the provider
 * with no wiring. Tests inject a seeded bag via the prop (the C2 seam).
 */
export function EngineProvider(props: {
  bag?: EnginePortBag;
  children: React.ReactNode;
}): React.JSX.Element {
  const bag = props.bag ?? browserEngineAdapters();
  return (
    <EngineContext.Provider value={bag}>
      {props.children}
    </EngineContext.Provider>
  );
}

/**
 * Read the engine `EnginePortBag` from context. Throws when called outside an
 * `<EngineProvider>` so a wiring mistake fails loudly at render time rather than
 * silently handing back `null` (the failure a screen hook would otherwise hit).
 */
export function useEngine(): EnginePortBag {
  const ctx = React.useContext(EngineContext);
  if (!ctx) {
    throw new Error(
      "useEngine() must be called inside <EngineProvider> -- ensure the " +
        "(coach) layout wraps the screen with the engine bag.",
    );
  }
  return ctx;
}
