/**
 * SignOutLink — full-document <a> to the WorkOS sign-out route (L1).
 *
 * Soft-nav via next/link is the failure mode this component exists to prevent.
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { SIGN_OUT_HREF, SignOutLink } from "./SignOutLink";

function dom(node: React.ReactElement): Document {
  return new JSDOM(renderToStaticMarkup(node)).window.document;
}

describe("SignOutLink", () => {
  it("renders a plain <a> to /api/auth/sign-out with returnTo=/", () => {
    const doc = dom(<SignOutLink />);
    const a = doc.querySelector('[data-testid="sign-out"]');
    expect(a?.tagName).toBe("A");
    expect(a?.getAttribute("href")).toBe(SIGN_OUT_HREF);
    expect(a?.textContent).toContain("Sign out");
  });

  it("iconOnly keeps an accessible name and drops the visible label", () => {
    const doc = dom(<SignOutLink iconOnly />);
    const a = doc.querySelector('[data-testid="sign-out"]');
    expect(a?.getAttribute("aria-label")).toBe("Sign out");
    expect(a?.textContent?.trim()).toBe("");
    expect(a?.querySelector("svg")).not.toBeNull();
  });
});
