/**
 * L1 tests for toAccuracyVM (E1b-D1 FR-3 / FR-5 / FR-6).
 */

import { describe, expect, it } from "vitest";
import { toAccuracyVM } from "./accuracy_vm";
import type { SkillAccuracyRow } from "../wire/engine_entities";

function row(
  sessionId: string,
  correct: number,
  total: number,
): SkillAccuracyRow {
  return { sessionId, correct, total };
}

describe("toAccuracyVM — E1b-D1", () => {
  it("FR-3: value + bars over last 6 sessions (newest-first, no pad)", () => {
    // 6 sessions newest-first: 100%, 50%, 75%, 0%, 100%, 50% → value = 15/24 = 63%
    const rows = [
      row("s6", 2, 2),
      row("s5", 1, 2),
      row("s4", 3, 4),
      row("s3", 0, 2),
      row("s2", 4, 4),
      row("s1", 1, 2),
    ];
    const vm = toAccuracyVM(rows);
    expect(vm).not.toBeNull();
    expect(vm!.valuePct).toBe(Math.round((100 * 11) / 16)); // 2+1+3+0+4+1=11; 2+2+4+2+4+2=16
    expect(vm!.bars).toEqual([100, 50, 75, 0, 100, 50]);
    expect(vm!.bars).toHaveLength(6);
  });

  it("FR-5: derived from attempt.correct tallies — never a mastery field", () => {
    // The function signature accepts ONLY SkillAccuracyRow (sessionId/correct/total).
    // Passing a mastery-shaped object is a type error; runtime: only correct/total used.
    const rows = [row("s1", 1, 2), row("s2", 2, 2)];
    const vm = toAccuracyVM(rows);
    expect(vm!.valuePct).toBe(75); // (1+2)/(2+2) = 75
    expect(vm!.bars).toEqual([50, 100]);
    // Source rows have no mastery key — the reduce cannot invent one.
    expect(
      Object.keys(rows[0]!).every((k) =>
        ["sessionId", "correct", "total"].includes(k),
      ),
    ).toBe(true);
    expect(vm).not.toHaveProperty("mastery");
  });

  it("FR-6: 3 sessions → exactly 3 bars, no padding", () => {
    const rows = [row("s3", 1, 1), row("s2", 0, 1), row("s1", 1, 2)];
    const vm = toAccuracyVM(rows);
    expect(vm!.bars).toEqual([100, 0, 50]);
    expect(vm!.bars).toHaveLength(3);
    expect(vm!.valuePct).toBe(50); // (1+0+1)/(1+1+2) = 50
  });

  it("empty rows → null (FR-1 self-omit input)", () => {
    expect(toAccuracyVM([])).toBeNull();
  });
});
