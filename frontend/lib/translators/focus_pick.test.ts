/**
 * focus_pick — pickFocusSkillId (weakest+due, scheduler-parity, pure).
 *
 * Moved here from use_dashboard.test.ts when the helper was extracted to a shared
 * translator (both the Dashboard focus banner and the Summary recommended-next
 * card select the same weakest+due skill). T4 table of the selection rule.
 */

import { describe, expect, it } from "vitest";
import { pickFocusSkillId } from "./focus_pick";
import type { SkillState } from "../wire/engine_entities";

const SUBJECT = "act-english";
const LEARNER = "maya";
const NOW = "2026-07-01T12:00:00.000Z";

function state(over: Partial<SkillState> = {}): SkillState {
  return {
    subject: SUBJECT,
    skill_id: "s-punc",
    learner_id: LEARNER,
    mastery: 0.5,
    last_seen: null,
    fsrs_stability: 1,
    fsrs_difficulty: 5,
    due_at: NOW,
    fsrs_card: null,
    ...over,
  } as SkillState;
}

describe("pickFocusSkillId — weakest+due, scheduler-parity, pure", () => {
  it("returns null when there are no skill_state rows (cold start)", () => {
    expect(pickFocusSkillId([], NOW)).toBeNull();
  });

  it("prefers a DUE skill with the lowest mastery over a non-due weaker one", () => {
    const states = [
      state({ skill_id: "s-punc", mastery: 0.3, due_at: NOW }), // due, weak
      state({ skill_id: "s-gram", mastery: 0.1, due_at: "2999-01-01T00:00:00.000Z" }), // weaker but NOT due
    ];
    expect(pickFocusSkillId(states, NOW)).toBe("s-punc");
  });

  it("falls back to the globally weakest when none are due", () => {
    const future = "2999-01-01T00:00:00.000Z";
    const states = [
      state({ skill_id: "s-punc", mastery: 0.6, due_at: future }),
      state({ skill_id: "s-gram", mastery: 0.2, due_at: future }),
    ];
    expect(pickFocusSkillId(states, NOW)).toBe("s-gram");
  });

  it("breaks mastery+due ties deterministically by skill_id", () => {
    const states = [
      state({ skill_id: "s-gram", mastery: 0.4, due_at: NOW }),
      state({ skill_id: "s-punc", mastery: 0.4, due_at: NOW }),
    ];
    // localeCompare tie-break: "s-gram" < "s-punc".
    expect(pickFocusSkillId(states, NOW)).toBe("s-gram");
  });
});
