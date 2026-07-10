/**
 * BP-3a — assemble_coach_context (FR-9, FR-10; red-first).
 */

import { describe, expect, it } from "vitest";
import { assembleCoachContext } from "./assemble_coach_context";
import type { Question, SkillState } from "../wire/engine_entities";

function question(over: Partial<Question> = {}): Question {
  return {
    id: "q1",
    subject: "act-english",
    skill_id: "s-punc",
    difficulty: 3,
    context_html: "The committee <u>have</u> decided.",
    stem: "Which choice is best?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "has", is_no_change: false },
    ],
    answer_letter: "A",
    per_choice_rationale: { A: "ok", B: "no" },
    why_correct_md: "…",
    why_tempted_md: "…",
    rule_md: "Collective nouns are singular.",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

const pin = {
  questionId: "q1",
  skillId: "s-punc",
  label: "Q4 · Commas",
};

describe("assembleCoachContext — failure / honesty first (FR-9)", () => {
  it("returns null when pin is null", () => {
    expect(
      assembleCoachContext({
        pin: null,
        question: question(),
        mode: "pre_submit",
        missesOnSkill: 3,
      }),
    ).toBeNull();
  });

  it("returns null when question failed to load", () => {
    expect(
      assembleCoachContext({
        pin,
        question: null,
        mode: "pre_submit",
      }),
    ).toBeNull();
  });

  it("returns null when question id mismatches pin", () => {
    expect(
      assembleCoachContext({
        pin,
        question: question({ id: "other" }),
        mode: "pre_submit",
      }),
    ).toBeNull();
  });

  it("omits misses_aggregate when missesOnSkill is null", () => {
    const ctx = assembleCoachContext({
      pin,
      question: question(),
      mode: "post_feedback",
      missesOnSkill: null,
    });
    expect(ctx).not.toBeNull();
    expect(ctx).not.toHaveProperty("misses_aggregate");
    expect(ctx).not.toHaveProperty("window");
  });
});

describe("assembleCoachContext — happy path (FR-10)", () => {
  it("includes ids, question, advisory mode, and misses without window", () => {
    const ctx = assembleCoachContext({
      pin,
      question: question(),
      mode: "post_feedback",
      missesOnSkill: 3,
    });
    expect(ctx).toMatchObject({
      mode: "post_feedback",
      question_id: "q1",
      skill_id: "s-punc",
      misses_aggregate: { skill_id: "s-punc", missed: 3 },
    });
    expect(ctx!.question.id).toBe("q1");
    expect(ctx!.misses_aggregate).not.toHaveProperty("window");
  });

  it("includes mastery_snapshot percent when SkillState present", () => {
    const states: SkillState[] = [
      {
        subject: "act-english",
        skill_id: "s-punc",
        learner_id: "maya",
        mastery: 0.42,
        last_seen: null,
        fsrs_stability: 0,
        fsrs_difficulty: 0,
        due_at: "2026-01-01T00:00:00Z",
        fsrs_card: null,
      },
    ];
    const ctx = assembleCoachContext({
      pin,
      question: question(),
      mode: "pre_submit",
      skillStates: states,
    });
    expect(ctx?.mastery_snapshot).toEqual({ "s-punc": 42 });
  });
});
