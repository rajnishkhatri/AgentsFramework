/**
 * test_scoring — pure raw→scale-band lookup (L1 node).
 *
 * Anchored to Test-01's worked convention (percent × 33 → equivalent raw → band).
 */

import { describe, it, expect } from "vitest";
import { englishScaleBand, ENGLISH_MAX_RAW } from "./test_scoring";

describe("englishScaleBand", () => {
  it("returns null for an empty section", () => {
    expect(englishScaleBand(0, 0)).toBeNull();
  });

  it("a perfect section maps to the top band", () => {
    // 48/48 → 100% × 33 = 33 → "32–32".
    expect(englishScaleBand(48, 48)).toBe("32–32");
  });

  it("zero correct maps to the lowest band", () => {
    expect(englishScaleBand(0, 48)).toBe("3–7");
  });

  it("a mid score lands on a plausible middle band", () => {
    // 24/48 = 50% × 33 ≈ 17 → floor row 15 → "11–15".
    expect(englishScaleBand(24, 48)).toBe("11–15");
  });

  it("scales onto the official English max raw (33)", () => {
    expect(ENGLISH_MAX_RAW).toBe(33);
    // 33/33 correct → 100% → top band, same as any 100%.
    expect(englishScaleBand(33, 33)).toBe("32–32");
  });
});
