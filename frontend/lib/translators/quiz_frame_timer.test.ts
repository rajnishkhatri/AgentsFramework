/**
 * formatElapsedFromStartedAt — Q-9 session-elapsed display helper (D1).
 *
 * Pure: takes `startedAtIso` + `nowMs`, returns `"m:ss"`. Clamps future clocks
 * and unparseable / null inputs to `"0:00"` (FR-Q9-4). No React, no I/O.
 */

import { describe, expect, it } from "vitest";
import { formatElapsedFromStartedAt } from "./quiz_frame_timer";

const T0_ISO = "2026-07-10T10:00:00.000Z";
const T0 = Date.parse(T0_ISO);

describe("formatElapsedFromStartedAt — FR-Q9-4", () => {
  it.each([
    { startedAtIso: T0_ISO, nowMs: T0, expected: "0:00" },
    { startedAtIso: T0_ISO, nowMs: T0 + 59_000, expected: "0:59" },
    { startedAtIso: T0_ISO, nowMs: T0 + 60_000, expected: "1:00" },
    { startedAtIso: T0_ISO, nowMs: T0 + 600_000, expected: "10:00" },
    { startedAtIso: T0_ISO, nowMs: T0 - 5_000, expected: "0:00" }, // future clock
    { startedAtIso: null, nowMs: T0, expected: "0:00" },
    { startedAtIso: "not-a-date", nowMs: T0, expected: "0:00" },
  ] as const)(
    "$startedAtIso @ $nowMs → $expected",
    ({ startedAtIso, nowMs, expected }) => {
      expect(formatElapsedFromStartedAt(startedAtIso, nowMs)).toBe(expected);
    },
  );
});
