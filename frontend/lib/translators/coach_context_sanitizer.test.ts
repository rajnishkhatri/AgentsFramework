/**
 * FR-19/FR-21 (ADR-0012 Amendment) — coach-context sanitizer, table-driven (T4).
 *
 * Failure path FIRST: the mode-spoofing case (client claims post_feedback,
 * no marker exists) must strip before any happy path passes. The lock test
 * keys the strip list to the `Question` wire entity itself, so a new
 * answer-bearing field breaks the TEST (forcing triage), not the contract.
 */

import { describe, expect, it } from "vitest";
import {
  Question,
  QUESTION_ANSWER_BEARING_FIELDS,
} from "@/lib/wire/engine_entities";
import {
  coachMarkerQuestionId,
  deriveCoachMode,
  hasCoachContext,
  sanitizeCoachRunBody,
} from "./coach_context_sanitizer";

const question = {
  id: "q-punc-1",
  subject: "english",
  skill_id: "s-punc",
  difficulty: 2,
  context_html: "The museum, <u>which opened in 1974 has</u> welcomed visitors.",
  stem: "Which choice best fixes the underlined portion?",
  choices: [{ letter: "A", label: "NO CHANGE", is_no_change: true }],
  answer_letter: "B",
  per_choice_rationale: { A: "unclosed clause" },
  why_correct_md: "closes the clause",
  why_tempted_md: "reads fine",
  rule_md: "pair of commas",
  item_type: "underlined-span-mc",
  misconception: null,
  reviewed: true,
  generated_by: "dev-seed",
};

function body(mode: string) {
  return {
    thread_id: "t1",
    agent_id: "subject-coach-english",
    input: {
      messages: [{ role: "user", content: "why is this wrong?" }],
      coach_context: {
        mode,
        question_id: "q-punc-1",
        skill_id: "s-punc",
        question,
      },
    },
  };
}

describe("mode derivation — marker store is the ONLY authority", () => {
  it("no marker ⇒ pre_submit even when the client claims post_feedback", () => {
    expect(deriveCoachMode({ hasSubmittedMarker: false })).toBe("pre_submit");
  });
  it("marker present ⇒ post_feedback (monotonic)", () => {
    expect(deriveCoachMode({ hasSubmittedMarker: true })).toBe("post_feedback");
  });
});

describe("sanitizeCoachRunBody — failure paths first", () => {
  it("SPOOF: client says post_feedback, derived pre_submit ⇒ all 4 fields stripped", () => {
    const out = sanitizeCoachRunBody(body("post_feedback"), "pre_submit");
    const q = (out.input as Record<string, unknown>).coach_context as Record<
      string,
      unknown
    >;
    const sanitized = q.question as Record<string, unknown>;
    for (const field of QUESTION_ANSWER_BEARING_FIELDS) {
      expect(sanitized).not.toHaveProperty(field);
    }
    // Non-answer-bearing fields survive.
    expect(sanitized.stem).toBe(question.stem);
    expect(sanitized.choices).toEqual(question.choices);
    // The advisory client mode is OVERWRITTEN with the derived mode.
    expect(q.mode).toBe("pre_submit");
  });

  it("pre_submit strip is idempotent and does not mutate the input body", () => {
    const original = body("pre_submit");
    const snapshot = JSON.parse(JSON.stringify(original));
    sanitizeCoachRunBody(original, "pre_submit");
    expect(original).toEqual(snapshot);
  });

  it("post_feedback ⇒ full question passes through (FR-21)", () => {
    const out = sanitizeCoachRunBody(body("post_feedback"), "post_feedback");
    const q = (out.input as Record<string, unknown>).coach_context as Record<
      string,
      unknown
    >;
    const passed = q.question as Record<string, unknown>;
    for (const field of QUESTION_ANSWER_BEARING_FIELDS) {
      expect(passed).toHaveProperty(field);
    }
    expect(q.mode).toBe("post_feedback");
  });

  it("body without coach_context is returned unchanged (chat runs unaffected)", () => {
    const plain = { thread_id: "t1", input: { messages: [] } };
    expect(sanitizeCoachRunBody(plain, "pre_submit")).toEqual(plain);
  });
});

describe("coachMarkerQuestionId — marker lookup key, fail-closed variants first (C1/C2)", () => {
  function bodyWith(context: Record<string, unknown>): unknown {
    return { thread_id: "t1", input: { coach_context: context } };
  }

  it.each([
    ["question_id missing", bodyWith({ mode: "post_feedback", question })],
    ["question_id empty string", bodyWith({ question_id: "", question })],
    ["question_id non-string", bodyWith({ question_id: 42, question })],
    [
      "question.id mismatch",
      bodyWith({ question_id: "q-other", question }), // question.id === q-punc-1
    ],
    ["no coach_context", { thread_id: "t1", input: {} }],
    ["unparseable body (null)", null],
  ])("%s ⇒ null (no marker lookup; pre_submit strip)", (_name, body) => {
    expect(coachMarkerQuestionId(body)).toBeNull();
  });

  it("valid + consistent question_id is returned", () => {
    expect(
      coachMarkerQuestionId(bodyWith({ question_id: "q-punc-1", question })),
    ).toBe("q-punc-1");
  });

  it("question_id without an embedded question record is still usable", () => {
    expect(coachMarkerQuestionId(bodyWith({ question_id: "q-punc-1" }))).toBe(
      "q-punc-1",
    );
  });

  it("hasCoachContext distinguishes coach bodies from plain chat bodies", () => {
    expect(hasCoachContext(bodyWith({ question_id: "q-punc-1" }))).toBe(true);
    expect(hasCoachContext({ thread_id: "t1", input: { messages: [] } })).toBe(
      false,
    );
    expect(hasCoachContext(null)).toBe(false);
  });
});

describe("lock — strip list keyed to the Question wire entity (FR-19 L1 lock)", () => {
  it("every strip-list field exists on the Question schema", () => {
    const keys = Object.keys(Question.shape);
    for (const field of QUESTION_ANSWER_BEARING_FIELDS) {
      expect(keys).toContain(field);
    }
  });

  it("Question schema keys are frozen — a NEW field forces answer-bearing triage here", () => {
    // If this fails you added a field to Question: decide whether it is
    // answer-bearing. If yes → add to QUESTION_ANSWER_BEARING_FIELDS; if
    // no → update this frozen list. Either way the decision is recorded.
    expect(Object.keys(Question.shape).sort()).toEqual(
      [
        "id",
        "subject",
        "skill_id",
        "difficulty",
        "context_html",
        "stem",
        "choices",
        "answer_letter",
        "per_choice_rationale",
        "why_correct_md",
        "why_tempted_md",
        "rule_md",
        "item_type",
        "reviewed",
        "generated_by",
      ].sort(),
    );
  });
});
