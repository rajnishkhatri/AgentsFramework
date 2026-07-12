/**
 * L1 tests for newestDueMiss (E1a FR-16a / FR-16b).
 */

import { describe, expect, it } from "vitest";
import type { Attempt, Question, SkillState } from "../wire/engine_entities";
import { newestDueMiss } from "./newest_due_miss";

const NOW = "2026-07-11T12:00:00.000Z";
const PAST = "2026-07-10T12:00:00.000Z";
const FUTURE = "2026-07-12T12:00:00.000Z";

function attempt(over: Partial<Attempt> = {}): Attempt {
  return {
    id: "a-1",
    subject: "act-english",
    session_id: "qs-1",
    question_id: "q-1",
    chosen_letter: "A",
    correct: false,
    elapsed_ms: 1000,
    created_at: PAST,
    used_hint: false,
    ...over,
  };
}

function question(over: Partial<Question> = {}): Question {
  return {
    id: "q-1",
    subject: "act-english",
    skill_id: "s-punc",
    difficulty: 2,
    context_html: "",
    stem: "",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "was", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: {},
    why_correct_md: "",
    why_tempted_md: "",
    rule_md: "",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "authored",
    ...over,
  };
}

function skillState(over: Partial<SkillState> = {}): SkillState {
  return {
    subject: "act-english",
    skill_id: "s-punc",
    learner_id: "maya",
    mastery: 0.49,
    last_seen: PAST,
    fsrs_stability: 1,
    fsrs_difficulty: 5,
    due_at: PAST,
    fsrs_card: null,
    ...over,
  };
}

describe("newestDueMiss — FR-16a / FR-16b", () => {
  it("(a) tagged newest-due → verbatim tag", () => {
    const tag = "deleting commas to shorten a which-clause";
    const got = newestDueMiss({
      misses: [attempt({ id: "a-new", question_id: "q-1" })],
      skillStates: [skillState({ due_at: PAST })],
      questions: [question({ misconception: tag })],
      nowISO: NOW,
    });
    expect(got).not.toBeNull();
    expect(got!.tag).toBe(tag);
    expect(got!.skillId).toBe("s-punc");
  });

  it("(b) no due miss → null", () => {
    const got = newestDueMiss({
      misses: [attempt()],
      skillStates: [skillState({ due_at: FUTURE })],
      questions: [question({ misconception: "some tag" })],
      nowISO: NOW,
    });
    expect(got).toBeNull();
  });

  it("(c) untagged due miss → null (tier-3)", () => {
    const got = newestDueMiss({
      misses: [attempt()],
      skillStates: [skillState({ due_at: PAST })],
      questions: [question({ misconception: null })],
      nowISO: NOW,
    });
    expect(got).toBeNull();
  });

  it("skips a newer non-due miss to reach an older due tagged miss", () => {
    const got = newestDueMiss({
      misses: [
        attempt({ id: "a-new", question_id: "q-fresh" }),
        attempt({ id: "a-old", question_id: "q-due" }),
      ],
      skillStates: [
        skillState({ skill_id: "s-gram", due_at: FUTURE }),
        skillState({ skill_id: "s-punc", due_at: PAST }),
      ],
      questions: [
        question({
          id: "q-fresh",
          skill_id: "s-gram",
          misconception: "should not win",
        }),
        question({
          id: "q-due",
          skill_id: "s-punc",
          misconception: "the due tag",
        }),
      ],
      nowISO: NOW,
    });
    expect(got?.tag).toBe("the due tag");
  });

  it("empty whitespace tag is treated as untagged (tier-3)", () => {
    const got = newestDueMiss({
      misses: [attempt()],
      skillStates: [skillState({ due_at: PAST })],
      questions: [question({ misconception: "   " })],
      nowISO: NOW,
    });
    expect(got).toBeNull();
  });
});
