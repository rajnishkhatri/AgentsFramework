/**
 * Vitest sibling for `check_bundle_budget.ts` (STUB mode).
 *
 * Today both prerequisites (`@next/bundle-analyzer` + `.bundle-baseline.json`)
 * are absent so the only deterministic path is the skipped branch. We
 * still exercise the missing-list completeness so a future installation
 * makes the test red until the real implementation lands.
 */

import { describe, expect, it } from "vitest";
import { checkBundleBudget } from "./check_bundle_budget";

describe("check_bundle_budget — STUB skipped path", () => {
  it("returns skipped:true with the documented reason today", () => {
    const r = checkBundleBudget("all");
    expect(r.skipped).toBe(true);
    expect(r.pass).toBe(true);
    expect(r.reason).toMatch(/baseline not committed/);
  });

  it("enumerates @next/bundle-analyzer + frontend/.bundle-baseline.json in missing[]", () => {
    const r = checkBundleBudget("all");
    expect(r.missing).toEqual(
      expect.arrayContaining(["@next/bundle-analyzer", "frontend/.bundle-baseline.json"]),
    );
  });

  it("preserves the requested route verbatim", () => {
    const r = checkBundleBudget("/chat");
    expect(r.route).toBe("/chat");
  });
});
