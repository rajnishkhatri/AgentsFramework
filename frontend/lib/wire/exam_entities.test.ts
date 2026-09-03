/**
 * L1 — Exam wire entities (FR-9). Failure paths first, then zod round-trip
 * + snapshot of a well-formed form / run / item / analytics payload.
 */

import { describe, expect, it } from "vitest";
import {
  AssetRef,
  ClientExamForm,
  ExamAnalytics,
  ExamForm,
  ExamPassage,
  ExamRun,
  ExamRunItem,
  ExamSectionAttempt,
} from "./exam_entities";

function question(over: Record<string, unknown> = {}) {
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
    reviewed: true,
    generated_by: "test@run1",
    reporting_category: "conventions-of-standard-english",
    scored: true,
    passage: null,
    ...over,
  };
}

function section(over: Record<string, unknown> = {}) {
  return {
    code: "english",
    title: "English",
    minutes: 18,
    choice_count: 4,
    directions: "Begin when you are told.",
    composite: true,
    scale_table: null,
    questions: [question()],
    ...over,
  };
}

function form(over: Record<string, unknown> = {}) {
  return {
    id: "test01",
    title: "Test 01",
    blueprint: "test01",
    composite_sections: ["english"],
    sections: [section()],
    ...over,
  };
}

describe("ExamForm — failure paths first (FR-9)", () => {
  it("rejects an unknown blueprint", () => {
    expect(() => ExamForm.parse(form({ blueprint: "sat" }))).toThrow();
  });

  it("rejects choice_count other than 4 or 5", () => {
    expect(() =>
      ExamForm.parse(form({ sections: [section({ choice_count: 3 })] })),
    ).toThrow();
  });

  it("rejects an unknown section code", () => {
    expect(() =>
      ExamForm.parse(form({ sections: [section({ code: "writing" })] })),
    ).toThrow();
  });
});

describe("ExamForm / ExamRun / ExamRunItem / ExamAnalytics — round-trip + snapshot", () => {
  it("parses a well-formed form and snapshots the wire shape", () => {
    const parsed = ExamForm.parse(form());
    expect(parsed.sections[0]!.questions[0]!.scored).toBe(true);
    expect(parsed).toMatchSnapshot();
  });

  it("round-trips ExamRun, ExamSectionAttempt, ExamRunItem, ExamAnalytics", () => {
    const run = ExamRun.parse({
      id: "run-1",
      learner_id: "learner-1",
      form_id: "test01",
      created_at: "2026-09-02T00:00:00.000Z",
      composite: null,
    });
    const attempt = ExamSectionAttempt.parse({
      run_id: "run-1",
      section_code: "english",
      status: "in_progress",
      started_at: "2026-09-02T00:00:00.000Z",
      finished_at: null,
      deadline_at: "2026-09-02T00:18:00.000Z",
      raw_correct: null,
      raw_scored_total: null,
      scale_score: null,
      time_remaining_ms_at_submit: null,
    });
    const item = ExamRunItem.parse({
      run_id: "run-1",
      section_code: "english",
      question_id: "q-1",
      ordinal: 1,
      chosen_letter: "B",
      correct: true,
      dwell_ms: 1200,
      visits: 1,
      answer_changes: 0,
      first_answered_at: "2026-09-02T00:00:05.000Z",
      dwell_at_first_answer_ms: 800,
      flagged_in_section: false,
      bookmarked: false,
      updated_at: "2026-09-02T00:00:05.000Z",
    });
    const analytics = ExamAnalytics.parse({
      scope: { learner_id: "learner-1", run_id: "run-1" },
      facets: [
        {
          kind: "subject",
          key: "english",
          items: 5,
          correct: 4,
          unanswered: 0,
          accuracy: 0.8,
          mean_dwell_ms: 1000,
          quadrants: {
            fast_right: 2,
            fast_wrong: 0,
            slow_right: 2,
            slow_wrong: 1,
          },
          label: "strength",
        },
      ],
      pacing: [
        {
          section_code: "english",
          unanswered: 0,
          trailing_unanswered: 0,
          time_remaining_ms_at_submit: 12_000,
          pct_over_2x_median_dwell: 0,
        },
      ],
      recommendations: [
        {
          rule: "revise_flagged",
          facet_ref: "subject:english",
          evidence: "1 flagged ∧ wrong",
          priority: 1,
        },
      ],
    });
    expect(run.composite).toBeNull();
    expect(attempt.status).toBe("in_progress");
    expect(item.dwell_ms).toBe(1200);
    expect(analytics.facets[0]!.label).toBe("strength");
  });
});

describe("ExamForm phase-2 wire (B0-1 / §4.1) — back-compat + ClientExamForm", () => {
  it("parses Test-01-shaped input unchanged (no image/passages/delivery)", () => {
    const parsed = ExamForm.parse(form());
    expect(parsed.delivery).toBe("client-bundled");
    expect(parsed.sections[0]!.passages).toEqual([]);
    expect(parsed.sections[0]!.questions[0]!.image).toBeNull();
  });

  it("round-trips AssetRef / ExamPassage / asset-served delivery", () => {
    const image = AssetRef.parse({
      store: "form-image",
      form_id: "pt2",
      key: "math/q-12.png",
    });
    const passage = ExamPassage.parse({
      label: "P1",
      title: "Figure 1",
      intro: null,
      text: null,
      image,
      question_numbers: [1, 2],
    });
    const parsed = ExamForm.parse(
      form({
        delivery: "asset-served",
        sections: [
          section({
            passages: [passage],
            questions: [question({ image })],
          }),
        ],
      }),
    );
    expect(parsed.delivery).toBe("asset-served");
    expect(parsed.sections[0]!.passages[0]!.label).toBe("P1");
    expect(parsed.sections[0]!.questions[0]!.image).toEqual(image);
  });

  it("ClientExamForm is .strict() and omits the four answer-bearing fields", () => {
    const clientSafe = {
      id: "pt2",
      title: "PT2",
      blueprint: "act-enhanced",
      composite_sections: ["english", "math", "reading"],
      delivery: "asset-served",
      sections: [
        {
          code: "english",
          title: "English",
          minutes: 35,
          choice_count: 4,
          directions: "Begin.",
          composite: true,
          scale_table: null,
          passages: [],
          questions: [
            {
              id: "q-1",
              subject: "act-english",
              skill_id: "s-gram",
              difficulty: 3,
              context_html: "<p>x</p>",
              stem: "stem",
              choices: [
                { letter: "A", label: "A", is_no_change: false },
                { letter: "B", label: "B", is_no_change: false },
                { letter: "C", label: "C", is_no_change: false },
                { letter: "D", label: "D", is_no_change: false },
              ],
              rule_md: "r",
              item_type: "mc",
              reviewed: true,
              generated_by: "test",
              reporting_category: null,
              scored: true,
              passage: null,
              image: null,
            },
          ],
        },
      ],
    };
    const parsed = ClientExamForm.parse(clientSafe);
    expect(parsed.delivery).toBe("asset-served");
    expect(() =>
      ClientExamForm.parse({
        ...clientSafe,
        sections: [
          {
            ...clientSafe.sections[0]!,
            questions: [
              {
                ...clientSafe.sections[0]!.questions[0]!,
                answer_letter: "B",
              },
            ],
          },
        ],
      }),
    ).toThrow();
    expect(() =>
      ClientExamForm.parse({ ...clientSafe, extra_key: true }),
    ).toThrow();
  });
});
