/**
 * weekly_sessions_vm — FR-2/8/11 (C1). Failure/edge rows first (TAP-4).
 */

import { describe, expect, it } from "vitest";
import type { QuizSession } from "../wire/engine_entities";
import { toWeeklySessionsVM } from "./weekly_sessions_vm";

function session(ended_at: string, id = "s1"): QuizSession {
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

function localISO(y: number, m0: number, d: number, h = 12, min = 0): string {
  return new Date(y, m0, d, h, min, 0, 0).toISOString();
}

describe("toWeeklySessionsVM — failure / edge (FR-2/8)", () => {
  it("empty_input_zero_of_three", () => {
    expect(toWeeklySessionsVM([], localISO(2026, 6, 10))).toEqual({
      count: 0,
      target: 3,
      label: "0 / 3 sessions",
    });
  });

  it("monday_start_week_math — Sunday belongs to previous week", () => {
    // 2026-07-12 is a Sunday; week containing it starts Monday 2026-07-06.
    // A session on Sunday 2026-07-05 is the PREVIOUS week's Sunday → excluded.
    const now = localISO(2026, 6, 12, 15); // Sunday Jul 12
    const prevSunday = localISO(2026, 6, 5, 12); // Sunday Jul 5
    const thisMonday = localISO(2026, 6, 6, 9); // Monday Jul 6
    expect(
      toWeeklySessionsVM([session(prevSunday, "old"), session(thisMonday, "in")], now)
        .count,
    ).toBe(1);
  });

  it("count_greater_than_target_label_caps_at_three_but_count_stays_real", () => {
    const now = localISO(2026, 6, 10, 18); // Friday
    const sessions = [1, 2, 3, 4, 5].map((n) =>
      session(localISO(2026, 6, 6 + (n % 5), 10), `s${n}`),
    );
    const vm = toWeeklySessionsVM(sessions, now);
    expect(vm.count).toBe(5);
    expect(vm.label).toBe("3 / 3 sessions");
  });

  it("sinceMonday_inclusive — session at Monday 00:00 local is counted", () => {
    const now = localISO(2026, 6, 10, 12); // Friday
    const mondayMidnight = localISO(2026, 6, 6, 0, 0); // Monday Jul 6 00:00
    expect(toWeeklySessionsVM([session(mondayMidnight)], now)).toEqual({
      count: 1,
      target: 3,
      label: "1 / 3 sessions",
    });
  });
});
