/**
 * W2-2 — exam scoring (FR-7, FR-8, FR-27, FR-28).
 * Raw over scored items; scale_score null when the table is absent;
 * composite = round(mean), .5 up, and null until every composite section
 * is submitted/expired. Injected Grader (FR-27); reducer does not grade.
 */

import { describe, expect, it } from "vitest";
import { ExactLetterGrader } from "@/lib/adapters/engine/grader/exact_letter_grader";
import type { Grader } from "@/lib/ports/engine/grader";
import type {
  ExamForm,
  ExamQuestion,
  ExamRunItem,
  ExamSection,
  ExamSectionAttempt,
  ExamSectionCode,
} from "@/lib/wire/exam_entities";
import { examComposite, scoreExamSection } from "./exam_scoring";

const grader = new ExactLetterGrader();

function question(over: Partial<ExamQuestion> = {}): ExamQuestion {
  return {
    id: "q-1",
    subject: "act-english",
    skill_id: "s-gram",
    difficulty: 3,
    context_html: "<p>The committee <u>were</u> unanimous.</p>",
    stem: "Which choice best fixes the underlined portion?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "was", is_no_change: false },
      { letter: "C", label: "have been", is_no_change: false },
      { letter: "D", label: "being", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: { A: "a", B: "b", C: "c", D: "d" },
    why_correct_md: "singular",
    why_tempted_md: "plural people",
    rule_md: "collective nouns",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "test@w2-2",
    reporting_category: "conventions-of-standard-english",
    scored: true,
    passage: null,
    ...over,
  };
}

function section(over: Partial<ExamSection> = {}): ExamSection {
  return {
    code: "english",
    title: "English",
    minutes: 18,
    choice_count: 4,
    directions: "Begin when you are told.",
    composite: true,
    scale_table: null,
    questions: [
      question({ id: "q-1", answer_letter: "B" }),
      question({ id: "q-2", answer_letter: "A" }),
      question({ id: "q-3", answer_letter: "C" }),
      question({ id: "q-4", answer_letter: "D", scored: false }),
    ],
    ...over,
  };
}

function item(
  questionId: string,
  chosen: string | null,
): Pick<ExamRunItem, "question_id" | "chosen_letter"> {
  return { question_id: questionId, chosen_letter: chosen };
}

function form(over: Partial<ExamForm> = {}): ExamForm {
  return {
    id: "legacy-4",
    title: "Legacy four-section",
    blueprint: "preact-secure-legacy",
    composite_sections: ["english", "math", "reading", "science"],
    sections: [],
    ...over,
  };
}

function attempt(
  sectionCode: ExamSectionCode,
  over: Partial<ExamSectionAttempt> = {},
): ExamSectionAttempt {
  return {
    run_id: "run-1",
    section_code: sectionCode,
    status: "not_started",
    started_at: null,
    finished_at: null,
    deadline_at: null,
    raw_correct: null,
    raw_scored_total: null,
    scale_score: null,
    time_remaining_ms_at_submit: null,
    ...over,
  };
}

function countingGrader(): { grader: Grader; calls: () => number } {
  let n = 0;
  const inner = new ExactLetterGrader();
  return {
    grader: {
      grade(q, a) {
        n += 1;
        return inner.grade(q, a);
      },
    },
    calls: () => n,
  };
}

describe("exam_scoring — FR-27 grade once; scored-only raw", () => {
  it("grade once; scored-only raw", () => {
    const counted = countingGrader();
    const sec = section();
    const result = scoreExamSection(
      sec,
      [
        item("q-1", "B"),
        item("q-2", "A"),
        item("q-3", null),
        item("q-4", "D"),
      ],
      counted.grader,
    );

    expect(counted.calls()).toBe(sec.questions.length);
    expect(result.grades).toEqual([
      { question_id: "q-1", correct: true },
      { question_id: "q-2", correct: true },
      { question_id: "q-3", correct: null },
      { question_id: "q-4", correct: true },
    ]);
    // q-4 is unscored: counted for review, not in raw/scale (spec §6).
    expect(result.raw_correct).toBe(2);
    expect(result.raw_scored_total).toBe(3);
    expect(result.percent).toBe(2 / 3);
  });

  it("unanswered scored items are 0, not negative (blank = 0)", () => {
    const result = scoreExamSection(
      section({ questions: [question({ id: "q-1" }), question({ id: "q-2" })] }),
      [item("q-1", null), item("q-2", null)],
      grader,
    );
    expect(result.grades.map((g) => g.correct)).toEqual([null, null]);
    expect(result.raw_correct).toBe(0);
    expect(result.raw_scored_total).toBe(2);
    expect(result.percent).toBe(0);
  });
});

describe("exam_scoring — FR-7 no scale table ⇒ scale null", () => {
  it("no scale table ⇒ scale null", () => {
    const result = scoreExamSection(
      section({ scale_table: null }),
      [item("q-1", "B"), item("q-2", "A"), item("q-3", "C"), item("q-4", "D")],
      grader,
    );
    expect(result.raw_correct).toBe(3);
    expect(result.raw_scored_total).toBe(3);
    expect(result.percent).toBe(1);
    expect(result.scale_score).toBeNull();
  });

  it("looks up scale from the table over scored raw only", () => {
    const result = scoreExamSection(
      section({
        scale_table: { "0": 1, "1": 4, "2": 8, "3": 12 },
      }),
      [
        item("q-1", "B"),
        item("q-2", "A"),
        item("q-3", "A"),
        item("q-4", "D"),
      ],
      grader,
    );
    // 2 scored correct (q-1, q-2); q-4 unscored correct must not select "3".
    expect(result.raw_correct).toBe(2);
    expect(result.scale_score).toBe(8);
  });

  it("missing scale-table row is honest null (AP-6), not a fabricated band", () => {
    const result = scoreExamSection(
      section({ scale_table: { "0": 1 } }),
      [item("q-1", "B"), item("q-2", "A"), item("q-3", "C"), item("q-4", "A")],
      grader,
    );
    expect(result.raw_correct).toBe(3);
    expect(result.scale_score).toBeNull();
  });
});

describe("exam_scoring — FR-8 composite null until all composite sections finished", () => {
  it("composite null until all composite sections finished", () => {
    const f = form();
    expect(
      examComposite(f, [
        attempt("english", { status: "submitted", scale_score: 20 }),
        attempt("math", { status: "in_progress", scale_score: 22 }),
        attempt("reading", { status: "not_started", scale_score: null }),
        attempt("science", { status: "not_started", scale_score: null }),
      ]),
    ).toBeNull();

    expect(
      examComposite(f, [
        attempt("english", { status: "submitted", scale_score: 20 }),
        attempt("math", { status: "expired", scale_score: 22 }),
        attempt("reading", { status: "submitted", scale_score: 24 }),
        attempt("science", { status: "not_started", scale_score: 18 }),
      ]),
    ).toBeNull();
  });
});

describe("exam_scoring — FR-28 composite = round(mean), .5 up", () => {
  it("computes composite = round(mean of finished composite scales), .5 up", () => {
    const f = form();
    expect(
      examComposite(f, [
        attempt("english", { status: "submitted", scale_score: 22 }),
        attempt("math", { status: "expired", scale_score: 23 }),
        attempt("reading", { status: "submitted", scale_score: 24 }),
        attempt("science", { status: "submitted", scale_score: 25 }),
      ]),
    ).toBe(24); // mean 23.5 → 24

    expect(
      examComposite(f, [
        attempt("english", { status: "submitted", scale_score: 20 }),
        attempt("math", { status: "submitted", scale_score: 21 }),
        attempt("reading", { status: "submitted", scale_score: 22 }),
        attempt("science", { status: "submitted", scale_score: 21 }),
      ]),
    ).toBe(21); // mean 21.0
  });

  it("excludes non-composite sections from the mean (Enhanced Science)", () => {
    const f = form({
      blueprint: "act-enhanced",
      composite_sections: ["english", "math", "reading"],
    });
    expect(
      examComposite(f, [
        attempt("english", { status: "submitted", scale_score: 20 }),
        attempt("math", { status: "submitted", scale_score: 21 }),
        attempt("reading", { status: "submitted", scale_score: 22 }),
        attempt("science", { status: "submitted", scale_score: 36 }),
      ]),
    ).toBe(21); // mean of 20/21/22; science ignored
  });

  it("composite is null when a finished composite section has no scale (FR-7)", () => {
    expect(
      examComposite(form({ composite_sections: ["english"] }), [
        attempt("english", { status: "submitted", scale_score: null }),
      ]),
    ).toBeNull();
  });
});
