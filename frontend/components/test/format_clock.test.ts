/**
 * format_clock — pure timer logic (L1 node, no fake timers).
 *
 * Edge-first: zero and negative ms clamp to "00:00"/expired; a duration over an
 * hour still formats (minutes are not capped at 59) so a mis-set duration is
 * visible, not silently wrapped.
 */

import { describe, it, expect } from "vitest";
import { formatClock, clockBand, WARNING_THRESHOLD_MS } from "./format_clock";

describe("formatClock", () => {
  it("formats 35 minutes as 35:00", () => {
    expect(formatClock(35 * 60_000)).toBe("35:00");
  });

  it("formats sub-minute values with padded seconds", () => {
    expect(formatClock(9_000)).toBe("00:09");
    expect(formatClock(65_000)).toBe("01:05");
  });

  it("clamps zero and negative to 00:00", () => {
    expect(formatClock(0)).toBe("00:00");
    expect(formatClock(-5_000)).toBe("00:00");
  });

  it("does not wrap minutes above 59", () => {
    expect(formatClock(75 * 60_000)).toBe("75:00");
  });
});

describe("clockBand", () => {
  it("is normal well above the warning threshold", () => {
    expect(clockBand(WARNING_THRESHOLD_MS + 1_000)).toBe("normal");
  });

  it("is warning at or under the threshold (but still > 0)", () => {
    expect(clockBand(WARNING_THRESHOLD_MS)).toBe("warning");
    expect(clockBand(1_000)).toBe("warning");
  });

  it("is expired at or below zero", () => {
    expect(clockBand(0)).toBe("expired");
    expect(clockBand(-1)).toBe("expired");
  });
});
