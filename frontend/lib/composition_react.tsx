/**
 * React-side of the composition root: AdapterProvider context + useAdapters hook.
 *
 * Lives next to `composition.ts` because it depends on the same concrete
 * adapter classes through the `PortBag` shape. Components consume the
 * context exclusively (no direct adapter imports anywhere else, statically
 * enforced by `tests/architecture/test_frontend_layering.test.ts`).
 */

"use client";

import * as React from "react";
import type { PortBag } from "./composition";

const AdapterContext = React.createContext<PortBag | null>(null);

export function AdapterProvider(props: {
  bag: PortBag;
  children: React.ReactNode;
}): React.JSX.Element {
  return (
    <AdapterContext.Provider value={props.bag}>
      {props.children}
    </AdapterContext.Provider>
  );
}

export function useAdapters(): PortBag {
  const ctx = React.useContext(AdapterContext);
  if (!ctx) {
    throw new Error(
      "useAdapters() must be called inside <AdapterProvider> -- ensure the " +
        "root layout wraps the app with the composed PortBag.",
    );
  }
  return ctx;
}
