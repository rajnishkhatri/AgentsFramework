/**
 * streak_vm — FR-2/3/4/6/7/11 (C1). Failure/edge rows first (TAP-4).
 */

import { describe, expect, it } from "vitest";
import type { QuizSession } from "../wire/engine_entities";
import { toStreakVM } from "./streak_vm";

function session(ended_at: string | null, id = "s1"): QuizSession {
  return {
    id,
    subject: "act-english",
    learner_id: "maya",
    mode: "adaptive",
    skill_focus: null,
    started_at: "2026-07-01T00:00:00.000Z",
    ended_at,
    score_correct: 1,
    score_total: 1,
    target_count: 30,
  };
}

/** Local wall-clock → ISO for the injected clock / ended_at. */
function localISO(y: number, m0: number, d: number, h = 12, min = 0): string {
  return new Date(y, m0, d, h, min, 0, 0).toISOString();
}

describe("toStreakVM — failure / edge (FR-2/3/4/6)", () => {
  it("empty_input_present_false", () => {
    expect(toStreakVM([], localISO(2026, 6, 10))).toEqual({
      present: false,
      days: 0,
    });
  });

  it("stale_sessions_return_present_false", () => {
    // All ended_at older than 48h from now → no today/yesterday bucket.
    const now = localISO(2026, 6, 10, 12);
    const stale = localISO(2026, 6, 7, 12); // 3 days earlier
    expect(toStreakVM([session(stale)], now)).toEqual({
      present: false,
      days: 0,
    });
  });

  it("inflight_session_excluded", () => {
    const now = localISO(2026, 6, 10, 12);
    const today = localISO(2026, 6, 10, 10);
    const vm = toStreakVM(
      [session(null, "open"), session(today, "closed")],
      now,
    );
    expect(vm).toEqual({ present: true, days: 1 });
  });

  it("midnight_boundary_deterministic", () => {
    // nowISO at local midnight — a session one minute earlier is previous day.
    const now = localISO(2026, 6, 10, 0, 0);
    const justBefore = localISO(2026, 6, 9, 23, 59);
    expect(toStreakVM([session(justBefore)], now)).toEqual({
      present: false,
      days: 0,
    });
  });
});

describe("toStreakVM — consecutive days (FR-7)", () => {
  it("one_session_today_equals_one_day_streak", () => {
    const now = localISO(2026, 6, 10, 18);
    const today = localISO(2026, 6, 10, 9);
    expect(toStreakVM([session(today)], now)).toEqual({
      present: true,
      days: 1,
    });
  });

  it("three_day_consecutive_returns_three", () => {
    const now = localISO(2026, 6, 10, 18);
    const sessions = [
      session(localISO(2026, 6, 10, 9), "d0"),
      session(localISO(2026, 6, 9, 9), "d1"),
      session(localISO(2026, 6, 8, 9), "d2"),
    ];
    expect(toStreakVM(sessions, now)).toEqual({ present: true, days: 3 });
  });

  it("three_days_with_gap_stops_at_first_gap", () => {
    const now = localISO(2026, 6, 10, 18);
    const sessions = [
      session(localISO(2026, 6, 10, 9), "d0"),
      // gap on Jul 9
      session(localISO(2026, 6, 8, 9), "d2"),
    ];
    expect(toStreakVM(sessions, now)).toEqual({ present: true, days: 1 });
  });

  // FR-9 (C1-fix): one gap resets streak beyond the gap — Jul 10+9 consecutive,
  // Jul 8 missing, Jul 7 present → days=2 (not 3, not 1).
  it("one_gap_resets_streak_beyond_gap", () => {
    const now = localISO(2026, 6, 10, 18);
    const sessions = [
      session(localISO(2026, 6, 10, 9), "d0"),
      session(localISO(2026, 6, 9, 9), "d1"),
      // gap on Jul 8
      session(localISO(2026, 6, 7, 9), "d3"),
    ];
    expect(toStreakVM(sessions, now)).toEqual({ present: true, days: 2 });
  });
});
