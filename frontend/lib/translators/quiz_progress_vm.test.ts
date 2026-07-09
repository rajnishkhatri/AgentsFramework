/**
 * S4 — quiz_progress_vm (FR-1..FR-6/FR-8, L1 pure, TAP-2 table-driven).
 * S5 — extends with `complete` (done-state reached?): FR-1/FR-4/FR-8 + edges.
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
      complete: false, // S5 FR-1: endless is never "reached"
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
      complete: false, // S5: 14 graded < 30 target → not reached
    });
  });
});

describe("toQuizProgressVM — S5 done-state (`complete`), failure/edge first", () => {
  it("FR-1 endless (target null): never complete, even at a high tally", () => {
    expect(toQuizProgressVM(99, "reviewing", null).complete).toBe(false);
  });

  it("FR-4 boundary: gradedTotal == target → complete; == target-1 → not", () => {
    expect(toQuizProgressVM(30, "reviewing", 30).complete).toBe(true);
    expect(toQuizProgressVM(29, "reviewing", 30).complete).toBe(false);
  });

  it("edge over-run: gradedTotal > target → still complete (>=, not ==)", () => {
    expect(toQuizProgressVM(31, "reviewing", 30).complete).toBe(true);
  });

  it("edge target==1: gradedTotal 1 → complete; 0 → not (no off-by-one)", () => {
    expect(toQuizProgressVM(1, "reviewing", 1).complete).toBe(true);
    expect(toQuizProgressVM(0, "reviewing", 1).complete).toBe(false);
  });

  it("FR-8 purity/offset: complete keys on raw gradedTotal, NOT display position", () => {
    // Same gradedTotal, different phase — `position` differs (answering = +1),
    // but `complete` must be identical (it uses gradedTotal, not position), so the
    // banner never false-fires one question early during the answering phase.
    expect(toQuizProgressVM(30, "answering", 30).complete).toBe(true);
    expect(toQuizProgressVM(30, "reviewing", 30).complete).toBe(true);
    // And it does NOT fire early: 29 graded while answering (position shows 30)
    // is still NOT complete — proves position-independence in the risky direction.
    expect(toQuizProgressVM(29, "answering", 30).position).toBe(30);
    expect(toQuizProgressVM(29, "answering", 30).complete).toBe(false);
  });
});
