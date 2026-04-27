/**
 * Pure-function tests for KPI threshold logic.
 *
 * Failure-first: every "neutral" / zero-data branch is asserted before any
 * green/amber/red row.  Table-driven where the threshold space is finite.
 */
import { describe, it, expect } from "vitest";
import {
  averageCost,
  chainValidTone,
  costTone,
  guardrailRejectTone,
  latencyTone,
  runCountTone,
} from "./kpi_thresholds";

describe("costTone", () => {
  it.each([
    [0, "green"],
    [0.99, "green"],
    [1.0, "amber"],
    [4.99, "amber"],
    [5.0, "red"],
    [50.0, "red"],
  ] as const)("$%s -> %s", (value, expected) => {
    expect(costTone(value)).toBe(expected);
  });
});

describe("latencyTone", () => {
  it("0 ms is neutral (no data)", () => {
    expect(latencyTone(0)).toBe("neutral");
  });
  it.each([
    [1, "green"],
    [9_999, "green"],
    [10_000, "amber"],
    [29_999, "amber"],
    [30_000, "red"],
    [60_000, "red"],
  ] as const)("%s ms -> %s", (value, expected) => {
    expect(latencyTone(value)).toBe(expected);
  });
});

describe("guardrailRejectTone", () => {
  it("0 pass-rate (no data) is neutral", () => {
    expect(guardrailRejectTone(0)).toBe("neutral");
  });
  it.each([
    [1.0, "green"],
    [0.995, "green"],
    [0.99, "amber"],
    [0.91, "amber"],
    [0.9, "red"],
    [0.5, "red"],
  ] as const)("pass=%s -> %s", (passRate, expected) => {
    expect(guardrailRejectTone(passRate)).toBe(expected);
  });
});

describe("chainValidTone", () => {
  it("0 chains is neutral (no data)", () => {
    expect(chainValidTone(0, 0)).toBe("neutral");
  });
  it("any invalid chain is red", () => {
    expect(chainValidTone(99, 1)).toBe("red");
  });
  it("100% valid is green", () => {
    expect(chainValidTone(5, 0)).toBe("green");
  });
});

describe("runCountTone", () => {
  it("is always neutral", () => {
    expect(runCountTone()).toBe("neutral");
  });
});

describe("averageCost", () => {
  it("returns null when total_runs is zero (failure-first)", () => {
    expect(averageCost(10.0, 0)).toBeNull();
  });
  it("returns total/runs when runs > 0", () => {
    expect(averageCost(0.6, 3)).toBeCloseTo(0.2);
  });
});
