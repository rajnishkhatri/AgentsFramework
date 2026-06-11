/**
 * Vitest sibling for `check_axe_a11y.ts` (STUB mode).
 *
 * Because the Storybook host is still absent today (the
 * `@axe-core/playwright` dependency itself landed with the e2e a11y
 * work), the only paths we can exercise are:
 *   - the skipped:true branch (rejection of premature use),
 *   - the missing[] enumeration completeness.
 */

import { describe, expect, it } from "vitest";
import { checkAxeA11y } from "./check_axe_a11y";

describe("check_axe_a11y — STUB skipped path", () => {
  it("returns skipped:true with the documented reason today", () => {
    const r = checkAxeA11y("all");
    expect(r.skipped).toBe(true);
    expect(r.pass).toBe(true);
    expect(r.reason).toMatch(/axe-core toolchain not installed/);
  });

  it("enumerates the missing prerequisites in the missing[] array", () => {
    const r = checkAxeA11y("all");
    expect(r.missing).toEqual(
      expect.arrayContaining([".storybook/", "storybook script in package.json"]),
    );
    // @axe-core/playwright is installed (e2e a11y tier), so it must NOT
    // be reported missing.
    expect(r.missing).not.toContain("@axe-core/playwright");
  });

  it("preserves the requested target verbatim in the result", () => {
    const r = checkAxeA11y("components/chat/Composer");
    expect(r.target).toBe("components/chat/Composer");
  });
});
