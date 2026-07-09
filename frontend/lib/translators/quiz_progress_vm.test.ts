/**
 * S4 — quiz_progress_vm (FR-1..FR-6/FR-8, L1 pure, TAP-2 table-driven).
 *
 * Pure map: (gradedTotal, phase, targetCount) → QuizProgressVM. Drives the
 * "Question N of M" top bar (ADR: none — in-pattern VM+component). No mocks.
 *
 * Failure/edge rows FIRST (TAP-4): endless (null target), over-run past M,
 * first-item (gradedTotal 0), exact-at-target boundary, and the loading-carry
 * (no reset/flicker) — then the happy path.
 */

import { describe, expect, it } from "vitest";
import { toQuizProgressVM } from "./quiz_progress_vm";

describe("toQuizProgressVM — failure/edge first", () => {
  it("FR-1 endless (target null): no denominator, unbounded, fraction 0", () => {
    const vm = toQuizProgressVM(6, "answering", null);
    expect(vm).toEqual({
      position: 7,
      total: null,
      bounded: false,
      fraction: 0,
    });
  });

  it("FR-2 over-run past target: bar clamps to 1, denominator dropped", () => {
    const vm = toQuizProgressVM(31, "answering", 30);
    expect(vm.position).toBe(32);
    expect(vm.fraction).toBe(1);
    expect(vm.total).toBeNull(); // "Question 32", not "32 of 30"
    expect(vm.bounded).toBe(true);
  });

  it("FR-2 boundary: exactly at target still shows the denominator", () => {
    const vm = toQuizProgressVM(29, "answering", 30);
    expect(vm.position).toBe(30);
    expect(vm.total).toBe(30); // "Question 30 of 30"
    expect(vm.fraction).toBe(1);
  });

  it("FR-3 first item (gradedTotal 0, answering): position is 1, not 0", () => {
    const vm = toQuizProgressVM(0, "answering", 30);
    expect(vm.position).toBe(1);
    expect(vm.total).toBe(30);
    expect(vm.fraction).toBeCloseTo(1 / 30, 10);
  });

  it("FR-4 advance-on-grade: answering = gradedTotal+1, reviewing = gradedTotal", () => {
    expect(toQuizProgressVM(5, "answering", 30).position).toBe(6);
    // reviewing shows the item you JUST graded (§0 honest default)
    expect(toQuizProgressVM(5, "reviewing", 30).position).toBe(5);
  });

  it("FR-6 loading carries the last position (no reset to 0/1)", () => {
    expect(toQuizProgressVM(5, "loading", 30).position).toBe(5);
    expect(toQuizProgressVM(5, "done", 30).position).toBe(5);
  });
});

describe("toQuizProgressVM — happy path", () => {
  it("mid-session bounded: position, denominator, and half-full bar", () => {
    const vm = toQuizProgressVM(14, "answering", 30);
    expect(vm).toEqual({
      position: 15,
      total: 30,
      bounded: true,
      fraction: 0.5,
    });
  });
});
