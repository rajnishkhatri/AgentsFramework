/**
 * Injected now() / monotonic-clock seam (spec §7, B0-6).
 *
 * Reducer + write-buffer take an `ExamClock`; tests inject a fake so dwell
 * and deadlines are deterministic. Production wires `createExamClock()`.
 */

export type ExamClock = {
  /** Wall clock — `first_answered_at`, server-offset sampling, ISO stamps. */
  readonly now: () => Date;
  /** Monotonic ms — dwell deltas. Never subtract wall-clock timestamps. */
  readonly monotonic: () => number;
};

/**
 * System clock. `performance.now` is preferred for dwell; `Date.now` is the
 * fallback when `performance` is missing (some Node test hosts). That fallback
 * is a coarser monotonic, not a fabricated dwell value (G9).
 */
export function createExamClock(overrides: Partial<ExamClock> = {}): ExamClock {
  return {
    now: overrides.now ?? (() => new Date()),
    monotonic:
      overrides.monotonic ??
      (() =>
        typeof performance !== "undefined" &&
        typeof performance.now === "function"
          ? performance.now()
          : Date.now()),
  };
}
