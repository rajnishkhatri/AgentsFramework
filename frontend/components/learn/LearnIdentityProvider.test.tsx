/**
 * LearnIdentityProvider + useLearnIdentity (FR-6).
 *
 * No @testing-library/react — renderToStaticMarkup + JSDOM (engine-provider pattern).
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  LearnIdentityProvider,
  useLearnIdentity,
} from "./LearnIdentityProvider";
import type { LearnIdentity } from "@/lib/learn/resolve_learn_identity";

const SAMPLE: LearnIdentity = {
  learnerId: "user_workos_1",
  displayName: "Rajnish",
  seedMode: "fresh",
};

function Probe(): React.JSX.Element {
  const id = useLearnIdentity();
  return React.createElement(
    "span",
    { "data-testid": "learn-id" },
    `${id.learnerId}|${id.displayName}|${id.seedMode}`,
  );
}

function dom(html: string): Document {
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

describe("LearnIdentityProvider", () => {
  it("useLearnIdentity throws outside the provider (no Garvit default)", () => {
    expect(() => renderToStaticMarkup(React.createElement(Probe))).toThrow(
      /LearnIdentityProvider/,
    );
  });

  it("useLearnIdentity returns the provided value inside the provider", () => {
    const html = renderToStaticMarkup(
      React.createElement(LearnIdentityProvider, {
        value: SAMPLE,
        children: React.createElement(Probe),
      }),
    );
    const marker = dom(html).querySelector('[data-testid="learn-id"]');
    expect(marker?.textContent).toBe("user_workos_1|Rajnish|fresh");
    expect(marker?.textContent).not.toContain("Garvit");
  });
});
