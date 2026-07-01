/**
 * Vitest sibling for `check_axe_a11y.ts` (STATIC mode).
 *
 * The Storybook host + `@storybook/addon-a11y` + `@axe-core/playwright`
 * have all landed (PS1). The stub's `assert(false)` tripwire — which
 * existed only to force this replacement the moment the toolchain arrived
 * — is now retired. In its place the checker performs a *static*
 * verification (its filename's contract: the static counterpart to the
 * dynamic `e2e/accessibility.spec.ts`): the Storybook a11y addon is
 * wired and stories exist for the addon's axe pass to cover.
 *
 * Failure paths first (TAP-4): the mis-wired (addon absent) result before
 * the happy path.
 */

import { describe, expect, it } from "vitest";
import { checkAxeA11y, staticAxeReadiness } from "./check_axe_a11y";

describe("check_axe_a11y — static readiness (failure path)", () => {
  it("reports a11y addon absence as a fail, not a silent pass", () => {
    const r = staticAxeReadiness({
      addons: ["@storybook/addon-docs"],
      storyCount: 3,
    });
    expect(r.pass).toBe(false);
    expect(r.skipped).toBe(false);
    expect(r.reason).toMatch(/addon-a11y/);
  });

  it("reports zero stories as a fail (nothing for axe to cover)", () => {
    const r = staticAxeReadiness({
      addons: ["@storybook/addon-a11y"],
      storyCount: 0,
    });
    expect(r.pass).toBe(false);
    expect(r.skipped).toBe(false);
    expect(r.reason).toMatch(/no stories/i);
  });
});

describe("check_axe_a11y — static readiness (happy path)", () => {
  it("passes when the a11y addon is wired and stories exist", () => {
    const r = staticAxeReadiness({
      addons: ["@storybook/addon-a11y", "@storybook/addon-docs"],
      storyCount: 12,
    });
    expect(r.pass).toBe(true);
    expect(r.skipped).toBe(false);
    expect(r.reason).toMatch(/wired/i);
  });
});

describe("check_axe_a11y — real repo state", () => {
  it("passes today: Storybook a11y addon + stories are present", () => {
    const r = checkAxeA11y("all");
    expect(r.skipped).toBe(false);
    expect(r.pass).toBe(true);
  });

  it("preserves the requested target verbatim in the result", () => {
    const r = checkAxeA11y("components/chat/Composer");
    expect(r.target).toBe("components/chat/Composer");
  });
});
