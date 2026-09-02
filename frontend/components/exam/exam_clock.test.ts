/**
 * B0-6 — injected now() / monotonic-clock seam (§7 determinism).
 * Reducer + write-buffer consume this contract; tests inject a fake clock.
 */

import { describe, expect, it } from "vitest";
import { createExamClock, type ExamClock } from "./exam_clock";

describe("exam_clock seam (spec §7)", () => {
  it("accepts injected now + monotonic and stays deterministic", () => {
    let wall = Date.parse("2026-09-02T00:00:00.000Z");
    let mono = 1000;
    const clock: ExamClock = {
      now: () => new Date(wall),
      monotonic: () => mono,
    };
    expect(clock.now().toISOString()).toBe("2026-09-02T00:00:00.000Z");
    expect(clock.monotonic()).toBe(1000);
    wall += 5_000;
    mono += 5_000;
    expect(clock.now().toISOString()).toBe("2026-09-02T00:00:05.000Z");
    expect(clock.monotonic()).toBe(6000);
  });

  it("createExamClock wires Date + performance.now (or a fallback monotonic)", () => {
    const clock = createExamClock();
    const a = clock.now().getTime();
    const m = clock.monotonic();
    expect(Number.isFinite(a)).toBe(true);
    expect(Number.isFinite(m)).toBe(true);
  });
});
