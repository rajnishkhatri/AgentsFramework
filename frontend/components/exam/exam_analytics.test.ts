/**
 * W2-3 — exam analytics (FR-30–33).
 * Facets / quadrants / ≥5-item labels / pacing / RULES fire-and-don't-fire /
 * finalized-runs-only. Pure module: does not grade (reducer `correct` stays
 * null until finish; this read model consumes persisted item fields).
 */

import { describe, expect, it } from "vitest";
import type {
  ExamQuestion,
  ExamRunItem,
  ExamSection,
  ExamSectionAttempt,
  ExamSectionCode,
} from "@/lib/wire/exam_entities";
import {
  CARELESS_FAST_WRONG_SHARE,
  LABEL_MIN_ITEMS,
  PACING_TRAILING_MIN,
  RULES,
  STRENGTH_ACC,
  WEAKNESS_ACC,
  examAnalytics,
} from "./exam_analytics";

function question(over: Partial<ExamQuestion> = {}): ExamQuestion {
  return {
    id: "q-1",
    subject: "act-english",
    skill_id: "s-gram",
    difficulty: 3,
    context_html: "<p>x</p>",
    stem: "stem",
    choices: [
      { letter: "A", label: "a", is_no_change: true },
      { letter: "B", label: "b", is_no_change: false },
      { letter: "C", label: "c", is_no_change: false },
      { letter: "D", label: "d", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: { A: "a", B: "b", C: "c", D: "d" },
    why_correct_md: "why",
    why_tempted_md: "tempted",
    rule_md: "rule",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "test@w2-3",
    reporting_category: "conventions",
    scored: true,
    passage: "p-1",
    image: null,
    ...over,
  };
}

function section(
  questions: ExamQuestion[],
  over: Partial<ExamSection> = {},
): ExamSection {
  return {
    code: "english",
    title: "English",
    minutes: 18,
    choice_count: 4,
    directions: "Begin when you are told.",
    composite: true,
    scale_table: null,
    passages: [],
    questions,
    ...over,
  };
}

function item(
  over: Partial<ExamRunItem> & Pick<ExamRunItem, "question_id">,
): ExamRunItem {
  return {
    run_id: "run-1",
    section_code: "english",
    ordinal: 0,
    chosen_letter: over.correct === false ? "A" : over.correct === true ? "B" : null,
    correct: null,
    dwell_ms: 0,
    visits: 1,
    answer_changes: 0,
    first_answered_at: over.correct === null || over.correct === undefined
      ? null
      : "2026-09-02T12:00:00.000Z",
    dwell_at_first_answer_ms: over.correct === null || over.correct === undefined
      ? null
      : 10,
    flagged_in_section: false,
    bookmarked: false,
    updated_at: "2026-09-02T12:00:00.000Z",
    ...over,
  };
}

function attempt(
  over: Partial<ExamSectionAttempt> = {},
): ExamSectionAttempt {
  return {
    run_id: "run-1",
    section_code: "english",
    status: "submitted",
    started_at: "2026-09-02T12:00:00.000Z",
    finished_at: "2026-09-02T12:18:00.000Z",
    deadline_at: "2026-09-02T12:18:00.000Z",
    raw_correct: null,
    raw_scored_total: null,
    scale_score: null,
    time_remaining_ms_at_submit: 12_000,
    ...over,
  };
}

function qs(
  n: number,
  extra: (i: number) => Partial<ExamQuestion> = () => ({}),
): ExamQuestion[] {
  return Array.from({ length: n }, (_, i) =>
    question({ id: `q-${i + 1}`, ...extra(i) }),
  );
}

function itemsFor(
  questions: ExamQuestion[],
  each: (i: number, q: ExamQuestion) => Partial<ExamRunItem>,
  runId = "run-1",
  sectionCode: ExamSectionCode = "english",
): ExamRunItem[] {
  return questions.map((q, i) =>
    item({
      run_id: runId,
      section_code: sectionCode,
      question_id: q.id,
      ordinal: i,
      ...each(i, q),
    }),
  );
}

function analyze(args: {
  questions: ExamQuestion[];
  each: (i: number, q: ExamQuestion) => Partial<ExamRunItem>;
  attempt?: Partial<ExamSectionAttempt>;
  runId?: string | null;
  learnerId?: string;
  extraItems?: ExamRunItem[];
  extraAttempts?: ExamSectionAttempt[];
  extraSections?: ExamSection[];
}) {
  const runId = args.runId === undefined ? "run-1" : args.runId;
  const items = itemsFor(args.questions, args.each);
  return examAnalytics({
    learnerId: args.learnerId ?? "learner-1",
    runId,
    items: [...items, ...(args.extraItems ?? [])],
    sections: [section(args.questions), ...(args.extraSections ?? [])],
    attempts: [
      attempt({ run_id: items[0]?.run_id ?? "run-1", ...args.attempt }),
      ...(args.extraAttempts ?? []),
    ],
  });
}

function facetOf(
  facets: ReturnType<typeof examAnalytics>["facets"],
  kind: string,
  key: string,
) {
  const hit = facets.find((f) => f.kind === kind && f.key === key);
  if (hit === undefined) {
    throw new Error(`missing facet ${kind}:${key}`);
  }
  return hit;
}

describe("exam_analytics — RULES-as-data", () => {
  it("exposes the phase-1 rules as a data table (not a branch ladder)", () => {
    expect(LABEL_MIN_ITEMS).toBe(5);
    expect(STRENGTH_ACC).toBe(0.8);
    expect(WEAKNESS_ACC).toBe(0.6);
    expect(PACING_TRAILING_MIN).toBe(3);
    expect(CARELESS_FAST_WRONG_SHARE).toBe(0.3);
    expect(RULES.map((r) => r.id)).toEqual([
      "pacing",
      "careless",
      "knowledge_gap",
      "revise_flagged",
    ]);
    for (const rule of RULES) {
      expect(typeof rule.applies).toBe("function");
      expect(typeof rule.priority).toBe("number");
    }
  });
});

describe("exam_analytics — FR-30 facets, quadrants, same-run median", () => {
  it("builds subject/category/skill/passage/difficulty facets with median-dwell quadrants", () => {
    const questions = [
      question({
        id: "q-1",
        reporting_category: "conventions",
        skill_id: "s-gram",
        passage: "p-1",
        difficulty: 2,
      }),
      question({
        id: "q-2",
        reporting_category: "conventions",
        skill_id: "s-gram",
        passage: "p-1",
        difficulty: 2,
      }),
      question({
        id: "q-3",
        reporting_category: "conventions",
        skill_id: "s-gram",
        passage: "p-1",
        difficulty: 2,
      }),
      question({
        id: "q-4",
        reporting_category: "rhetoric",
        skill_id: "s-org",
        passage: "p-2",
        difficulty: 4,
      }),
      question({
        id: "q-5",
        reporting_category: "rhetoric",
        skill_id: "s-org",
        passage: "p-2",
        difficulty: 4,
      }),
      question({
        id: "q-6",
        reporting_category: "rhetoric",
        skill_id: "s-org",
        passage: null,
        difficulty: 4,
      }),
    ];
    const dwells = [100, 200, 300, 400, 500, 600];
    const result = analyze({
      questions,
      each: (i) => ({
        correct: i < 3,
        chosen_letter: i < 3 ? "B" : "A",
        dwell_ms: dwells[i] ?? 0,
      }),
    });

    const subject = facetOf(result.facets, "subject", "english");
    expect(subject.items).toBe(6);
    expect(subject.correct).toBe(3);
    expect(subject.unanswered).toBe(0);
    expect(subject.accuracy).toBe(0.5);
    expect(subject.mean_dwell_ms).toBe(350);
    // median of 100..600 = 350; fast = below, slow = at-or-above
    expect(subject.quadrants).toEqual({
      fast_right: 3,
      fast_wrong: 0,
      slow_right: 0,
      slow_wrong: 3,
    });
    expect(subject.label).toBe("weakness");

    const conv = facetOf(result.facets, "category", "conventions");
    expect(conv.items).toBe(3);
    expect(conv.correct).toBe(3);
    expect(conv.label).toBe("insufficient_data");

    expect(facetOf(result.facets, "skill", "s-gram").items).toBe(3);
    expect(facetOf(result.facets, "passage", "p-1").items).toBe(3);
    expect(facetOf(result.facets, "passage", "p-2").items).toBe(2);
    expect(result.facets.some((f) => f.kind === "passage" && f.key === "")).toBe(
      false,
    );
    expect(facetOf(result.facets, "difficulty", "2").items).toBe(3);
    expect(facetOf(result.facets, "difficulty", "4").items).toBe(3);

    expect(result.scope).toEqual({ learner_id: "learner-1", run_id: "run-1" });
  });

  it("classifies each item against its own run+section median (not a global median)", () => {
    const questions = qs(2);
    const run1 = itemsFor(questions, (i) => ({
      correct: i === 0,
      chosen_letter: i === 0 ? "B" : "A",
      dwell_ms: i === 0 ? 10 : 100,
    }), "run-1");
    const run2 = itemsFor(questions, (i) => ({
      correct: i === 0,
      chosen_letter: i === 0 ? "B" : "A",
      dwell_ms: i === 0 ? 200 : 300,
    }), "run-2");
    const result = examAnalytics({
      learnerId: "learner-1",
      runId: null,
      items: [...run1, ...run2],
      sections: [section(questions)],
      attempts: [
        attempt({ run_id: "run-1" }),
        attempt({ run_id: "run-2" }),
      ],
    });
    // run-1 median 55 → 10 fast_right, 100 slow_wrong
    // run-2 median 250 → 200 fast_right, 300 slow_wrong
    // a global median (150) would flip run-1's 100 into fast_wrong
    const subject = facetOf(result.facets, "subject", "english");
    expect(subject.quadrants).toEqual({
      fast_right: 2,
      fast_wrong: 0,
      slow_right: 0,
      slow_wrong: 2,
    });
    expect(result.scope.run_id).toBeNull();
  });

  it("leaves quadrants null when median dwell is undefined (one item, or all dwell 0)", () => {
    const one = analyze({
      questions: qs(1),
      each: () => ({ correct: false, chosen_letter: "A", dwell_ms: 900 }),
    });
    expect(facetOf(one.facets, "subject", "english").quadrants).toBeNull();

    const zeros = analyze({
      questions: qs(5),
      each: () => ({ correct: false, chosen_letter: "A", dwell_ms: 0 }),
    });
    expect(facetOf(zeros.facets, "subject", "english").quadrants).toBeNull();
    expect(zeros.recommendations.some((r) => r.rule === "careless")).toBe(false);
    expect(zeros.recommendations.some((r) => r.rule === "knowledge_gap")).toBe(
      false,
    );
  });
});

describe("exam_analytics — FR-30 finalized-runs-only", () => {
  it("ignores in-progress attempts even when their items would change labels", () => {
    const finishedQs = qs(5);
    const finished = itemsFor(finishedQs, () => ({
      correct: true,
      chosen_letter: "B",
      dwell_ms: 100,
    }), "run-fin");
    const liveQs = qs(5, (i) => ({ id: `live-${i + 1}` }));
    const live = itemsFor(liveQs, () => ({
      correct: null,
      chosen_letter: null,
      dwell_ms: 50,
    }), "run-live");
    const result = examAnalytics({
      learnerId: "learner-1",
      runId: null,
      items: [...finished, ...live],
      sections: [section(finishedQs), section(liveQs)],
      attempts: [
        attempt({ run_id: "run-fin", status: "submitted" }),
        attempt({ run_id: "run-live", status: "in_progress" }),
      ],
    });
    const subject = facetOf(result.facets, "subject", "english");
    expect(subject.items).toBe(5);
    expect(subject.correct).toBe(5);
    expect(subject.unanswered).toBe(0);
    expect(subject.label).toBe("strength");
    expect(result.pacing).toHaveLength(1);
    expect(result.pacing[0]?.unanswered).toBe(0);
  });
});

describe("exam_analytics — FR-31 pacing", () => {
  it("reports unanswered, trailing last-N-blank, time remaining, and % over 2× median", () => {
    const questions = qs(8);
    const result = analyze({
      questions,
      attempt: { time_remaining_ms_at_submit: 0, status: "expired" },
      each: (i) => {
        const blank = i >= 5;
        return {
          correct: blank ? null : true,
          chosen_letter: blank ? null : "B",
          dwell_ms: i >= 6 ? 500 : 100,
        };
      },
    });
    expect(result.pacing).toEqual([
      {
        section_code: "english",
        unanswered: 3,
        trailing_unanswered: 3,
        time_remaining_ms_at_submit: 0,
        // dwells 100×6 + 500×2; median = 100; 2× = 200; 2/8 over
        pct_over_2x_median_dwell: 2 / 8,
      },
    ]);
  });

  it("counts a middle blank as unanswered but not trailing", () => {
    const questions = qs(5);
    const result = analyze({
      questions,
      each: (i) => ({
        correct: i === 2 ? null : true,
        chosen_letter: i === 2 ? null : "B",
        dwell_ms: 100 + i,
      }),
    });
    expect(result.pacing[0]?.unanswered).toBe(1);
    expect(result.pacing[0]?.trailing_unanswered).toBe(0);
  });
});

describe("exam_analytics — FR-32 ≥5-item labels", () => {
  it("never labels strength/weakness from fewer than 5 items", () => {
    const four = analyze({
      questions: qs(4),
      each: () => ({ correct: true, chosen_letter: "B", dwell_ms: 80 + 10 }),
    });
    expect(facetOf(four.facets, "subject", "english").label).toBe(
      "insufficient_data",
    );
    expect(facetOf(four.facets, "subject", "english").accuracy).toBe(1);
  });

  it("labels strength at accuracy ≥ 0.80 with ≥ 5 items", () => {
    const result = analyze({
      questions: qs(5),
      each: (i) => ({
        correct: i < 4,
        chosen_letter: i < 4 ? "B" : "A",
        dwell_ms: 100 + i * 10,
      }),
    });
    expect(facetOf(result.facets, "subject", "english").accuracy).toBe(0.8);
    expect(facetOf(result.facets, "subject", "english").label).toBe("strength");
  });

  it("labels weakness at accuracy ≤ 0.60 with ≥ 5 items", () => {
    const result = analyze({
      questions: qs(5),
      each: (i) => ({
        correct: i < 3,
        chosen_letter: i < 3 ? "B" : "A",
        dwell_ms: 100 + i * 10,
      }),
    });
    expect(facetOf(result.facets, "subject", "english").accuracy).toBe(0.6);
    expect(facetOf(result.facets, "subject", "english").label).toBe("weakness");
  });

  it("does not claim strength or weakness in the mid band (0.60 < acc < 0.80)", () => {
    const result = analyze({
      questions: qs(7),
      each: (i) => ({
        correct: i < 5,
        chosen_letter: i < 5 ? "B" : "A",
        dwell_ms: 100 + i * 10,
      }),
    });
    expect(facetOf(result.facets, "subject", "english").accuracy).toBeCloseTo(
      5 / 7,
    );
    expect(facetOf(result.facets, "subject", "english").label).toBe(
      "insufficient_data",
    );
  });

  it("keeps all-unanswered facets as insufficient_data (not a fabricated weakness)", () => {
    const result = analyze({
      questions: qs(5),
      attempt: { status: "expired", time_remaining_ms_at_submit: 0 },
      each: () => ({ correct: null, chosen_letter: null, dwell_ms: 0 }),
    });
    expect(facetOf(result.facets, "subject", "english").unanswered).toBe(5);
    expect(facetOf(result.facets, "subject", "english").label).toBe(
      "insufficient_data",
    );
    expect(result.recommendations.map((r) => r.rule)).toEqual(["pacing"]);
  });
});

describe("exam_analytics — FR-33 recommendation rules fire / don't fire", () => {
  it("fires pacing when trailing unanswered ≥ 3, and not when it is 2", () => {
    const fire = analyze({
      questions: qs(5),
      each: (i) => ({
        correct: i < 2 ? true : null,
        chosen_letter: i < 2 ? "B" : null,
        dwell_ms: 100 + i,
      }),
    });
    expect(fire.pacing[0]?.trailing_unanswered).toBe(3);
    expect(fire.recommendations.some((r) => r.rule === "pacing")).toBe(true);

    const skip = analyze({
      questions: qs(5),
      each: (i) => ({
        correct: i < 3 ? true : null,
        chosen_letter: i < 3 ? "B" : null,
        dwell_ms: 100 + i,
      }),
    });
    expect(skip.pacing[0]?.trailing_unanswered).toBe(2);
    expect(skip.recommendations.some((r) => r.rule === "pacing")).toBe(false);
  });

  it("fires careless when fast_wrong ≥ 30% of wrong; not below, not when quadrants null", () => {
    // 10 items, median = 55; fast < 55: dwells 10..50; slow: 60..100
    // 3 fast_wrong + 2 slow_wrong = 5 wrong → fast share 0.60 ≥ 0.30
    const fireQs = qs(10);
    const fire = analyze({
      questions: fireQs,
      each: (i) => {
        const dwell = (i + 1) * 10;
        const wrong = i < 3 || i >= 8;
        return {
          correct: !wrong,
          chosen_letter: wrong ? "A" : "B",
          dwell_ms: dwell,
        };
      },
    });
    const fireQ = facetOf(fire.facets, "subject", "english").quadrants;
    expect(fireQ).toEqual({
      fast_right: 2,
      fast_wrong: 3,
      slow_right: 3,
      slow_wrong: 2,
    });
    expect(fire.recommendations.some((r) => r.rule === "careless")).toBe(true);

    // 1 fast_wrong + 4 slow_wrong = 5 wrong → share 0.20 < 0.30
    const skip = analyze({
      questions: qs(10),
      each: (i) => {
        const dwell = (i + 1) * 10;
        const wrong = i === 4 || i >= 6;
        return {
          correct: !wrong,
          chosen_letter: wrong ? "A" : "B",
          dwell_ms: dwell,
        };
      },
    });
    const skipQ = facetOf(skip.facets, "subject", "english").quadrants;
    expect(skipQ).toEqual({
      fast_right: 4,
      fast_wrong: 1,
      slow_right: 1,
      slow_wrong: 4,
    });
    expect(skip.recommendations.some((r) => r.rule === "careless")).toBe(false);

    const noMedian = analyze({
      questions: qs(1),
      each: () => ({ correct: false, chosen_letter: "A", dwell_ms: 800 }),
    });
    expect(noMedian.recommendations.some((r) => r.rule === "careless")).toBe(
      false,
    );
  });

  it("fires knowledge_gap on a weakness facet whose items are majority slow_wrong", () => {
    // 9 items, median = 50; 3 fast_right + 6 slow_wrong → acc 0.333 weakness
    const fire = analyze({
      questions: qs(9),
      each: (i) => {
        const dwell = (i + 1) * 10;
        const right = i < 3;
        return {
          correct: right,
          chosen_letter: right ? "B" : "A",
          dwell_ms: dwell,
        };
      },
    });
    const q = facetOf(fire.facets, "subject", "english");
    expect(q.label).toBe("weakness");
    expect(q.quadrants).toEqual({
      fast_right: 3,
      fast_wrong: 1,
      slow_right: 0,
      slow_wrong: 5,
    });
    // 5/9 is not a majority of items — slow_wrong majority = of the facet's items
    // 5 slow_wrong vs 4 others is a majority. Pin the intended meaning.
    expect(fire.recommendations.some((r) => r.rule === "knowledge_gap")).toBe(
      true,
    );

    const notMajority = analyze({
      questions: qs(9),
      each: (i) => {
        const dwell = (i + 1) * 10;
        // 3 slow_right (70,80,90) + 6 mixed wrongs, only 2 slow_wrong
        const right = i >= 6;
        return {
          correct: right,
          chosen_letter: right ? "B" : "A",
          dwell_ms: dwell,
        };
      },
    });
    expect(facetOf(notMajority.facets, "subject", "english").label).toBe(
      "weakness",
    );
    expect(
      notMajority.recommendations.some((r) => r.rule === "knowledge_gap"),
    ).toBe(false);
  });

  it("fires revise_flagged when flagged ∧ wrong ≥ 1, and not when flagged items are right", () => {
    const fire = analyze({
      questions: qs(5),
      each: (i) => ({
        correct: i !== 0,
        chosen_letter: i !== 0 ? "B" : "A",
        dwell_ms: 80 + i * 10,
        flagged_in_section: i === 0,
      }),
    });
    expect(fire.recommendations.some((r) => r.rule === "revise_flagged")).toBe(
      true,
    );

    const skip = analyze({
      questions: qs(5),
      each: (i) => ({
        correct: true,
        chosen_letter: "B",
        dwell_ms: 80 + i * 10,
        flagged_in_section: i === 0,
      }),
    });
    expect(skip.recommendations.some((r) => r.rule === "revise_flagged")).toBe(
      false,
    );
  });

  it("emits no filler advice when no rule fires", () => {
    const result = analyze({
      questions: qs(5),
      each: (i) => ({
        correct: true,
        chosen_letter: "B",
        dwell_ms: 80 + i * 10,
      }),
    });
    expect(facetOf(result.facets, "subject", "english").label).toBe("strength");
    expect(result.recommendations).toEqual([]);
  });

  it("orders recommendations by RULES priority (deterministic)", () => {
    const result = analyze({
      questions: qs(9),
      each: (i) => {
        const dwell = (i + 1) * 10;
        const right = i < 3;
        return {
          correct: right,
          chosen_letter: right ? "B" : "A",
          dwell_ms: dwell,
          flagged_in_section: i === 8,
        };
      },
    });
    const rules = result.recommendations.map((r) => r.rule);
    const order = RULES.map((r) => r.id);
    const ranks = rules.map((id) => order.indexOf(id));
    expect(ranks).toEqual([...ranks].sort((a, b) => a - b));
    for (const rec of result.recommendations) {
      expect(rec.evidence.length).toBeGreaterThan(0);
      expect(rec.facet_ref.length).toBeGreaterThan(0);
    }
  });
});
