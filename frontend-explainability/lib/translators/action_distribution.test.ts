/**
 * Translator tests — table-driven, one row per fail_action.
 *
 * Failure-first: empty input renders no slices; undefined-action input becomes
 * an explicit "unspecified" bucket so the chart never silently drops failures.
 *
 * Rule T1 spirit: this translator has no external imports beyond `wire/`.
 */
import { describe, it, expect } from "vitest";
import {
  failActionDistributionToSlices,
  type ActionSlice,
} from "./action_distribution";

interface TableRow {
  label: string;
  input: Record<string, number>;
  expected: ActionSlice[];
}

describe("failActionDistributionToSlices — failure paths", () => {
  it("returns [] for an empty distribution", () => {
    expect(failActionDistributionToSlices({})).toEqual([]);
  });

  it("ignores zero or negative counts (failure-first guard against bad data)", () => {
    expect(failActionDistributionToSlices({ reject: 0, escalate: -2 })).toEqual([]);
  });

  it("buckets a count keyed by the empty string into 'unspecified'", () => {
    expect(failActionDistributionToSlices({ "": 3 })).toEqual([
      {
        action: "unspecified",
        count: 3,
        share: 1.0,
        color: "neutral",
      },
    ]);
  });
});

const TABLE: TableRow[] = [
  {
    label: "single reject",
    input: { reject: 4 },
    expected: [
      { action: "reject", count: 4, share: 1.0, color: "danger" },
    ],
  },
  {
    label: "two-action mix",
    input: { reject: 3, redact: 1 },
    expected: [
      { action: "reject", count: 3, share: 0.75, color: "danger" },
      { action: "redact", count: 1, share: 0.25, color: "warning" },
    ],
  },
  {
    label: "three-action ordering by count desc, ties alpha",
    input: { escalate: 2, reject: 2, retry: 1 },
    expected: [
      { action: "escalate", count: 2, share: 0.4, color: "warning" },
      { action: "reject", count: 2, share: 0.4, color: "danger" },
      { action: "retry", count: 1, share: 0.2, color: "info" },
    ],
  },
  {
    label: "unknown action falls back to neutral colour",
    input: { quarantine: 1 },
    expected: [
      { action: "quarantine", count: 1, share: 1.0, color: "neutral" },
    ],
  },
];

describe.each(TABLE)("failActionDistributionToSlices — $label", (row) => {
  it("produces the expected slices", () => {
    expect(failActionDistributionToSlices(row.input)).toEqual(row.expected);
  });
});
