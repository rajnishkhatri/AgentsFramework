/**
 * Vitest sibling for `check_axe_a11y.ts` (STUB mode).
 *
 * Because the toolchain is intentionally absent today, the only paths we
 * can exercise are:
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
      expect.arrayContaining(["@axe-core/playwright", ".storybook/", "storybook script in package.json"]),
    );
  });

  it("preserves the requested target verbatim in the result", () => {
    const r = checkAxeA11y("components/chat/Composer");
    expect(r.target).toBe("components/chat/Composer");
  });
});
