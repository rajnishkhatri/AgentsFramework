/**
 * W1-7 — DrizzleExamRunRepo (FR-2 finish-once + FR-12 begin-conflict).
 *
 * Runs against InMemoryEngineDb. Port conformance is structural (P7);
 * these rows pin the adapter's behavioral contract.
 */

import { describe, expect, it } from "vitest";
import { ExactLetterGrader } from "../grader/exact_letter_grader";
import { InMemoryEngineDb } from "../db/in_memory_engine_db";
import { EngineRepoError } from "../../../ports/engine/errors";
import type {
  ExamForm,
  ExamQuestion,
  ExamRunItem,
} from "../../../wire/exam_entities";
import { DrizzleExamRunRepo } from "./drizzle_exam_run_repo";

const LEARNER = "learner-1";
const OTHER = "other-learner";
const NOW = new Date("2026-09-02T12:00:00.000Z");

function question(over: Partial<ExamQuestion> = {}): ExamQuestion {
  return {
    id: "q-1",
    subject: "act-english",
    skill_id: "s-punct",
    difficulty: 2,
    context_html: "x",
    stem: "y",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "b", is_no_change: false },
    ],
    answer_letter: "A",
    per_choice_rationale: {},
    why_correct_md: "",
    why_tempted_md: "",
    rule_md: "",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "test",
    reporting_category: null,
    scored: true,
    passage: null,
    image: null,
    ...over,
  };
}

function twoSectionForm(): ExamForm {
  return {
    id: "two-section",
    title: "Two section",
    blueprint: "test01",
    composite_sections: ["english"],
    delivery: "client-bundled",
    sections: [
      {
        code: "english",
        title: "English",
        minutes: 10,
        choice_count: 4,
        directions: "d",
        composite: true,
        scale_table: null,
        passages: [],
        questions: [question()],
      },
      {
        code: "math",
        title: "Math",
        minutes: 15,
        choice_count: 4,
        directions: "d",
        composite: false,
        scale_table: null,
        passages: [],
        questions: [question({ id: "q-math" })],
      },
    ],
  };
}

function repo(db = new InMemoryEngineDb()) {
  const form = twoSectionForm();
  return {
    db,
    form,
    repo: new DrizzleExamRunRepo({
      db,
      grader: new ExactLetterGrader(),
      getForm: () => form,
      newId: () => "run-1",
      now: () => NOW,
    }),
  };
}

function item(over: Partial<ExamRunItem> = {}): ExamRunItem {
  return {
    run_id: "run-1",
    section_code: "english",
    question_id: "q-1",
    ordinal: 0,
    chosen_letter: "A",
    correct: null,
    dwell_ms: 100,
    visits: 1,
    answer_changes: 0,
    first_answered_at: NOW.toISOString(),
    dwell_at_first_answer_ms: 80,
    flagged_in_section: false,
    bookmarked: false,
    updated_at: NOW.toISOString(),
    ...over,
  };
}

describe("DrizzleExamRunRepo (W1-7 / FR-2 / FR-12)", () => {
  it("startRun persists a learner-scoped run", async () => {
    const { repo: r } = repo();
    const run = await r.startRun({ learnerId: LEARNER, formId: "two-section" });
    expect(run.id).toBe("run-1");
    expect(run.learner_id).toBe(LEARNER);
    expect(run.form_id).toBe("two-section");
    expect(await r.getRun({ learnerId: LEARNER, runId: "run-1" })).toEqual(run);
    expect(await r.getRun({ learnerId: OTHER, runId: "run-1" })).toBeNull();
  });

  it("beginSection refuse a second in-progress section on the same run (FR-12)", async () => {
    const { repo: r } = repo();
    await r.startRun({ learnerId: LEARNER, formId: "two-section" });
    const first = await r.beginSection({
      learnerId: LEARNER,
      runId: "run-1",
      sectionCode: "english",
    });
    expect(first.status).toBe("in_progress");
    expect(first.started_at).toBe(NOW.toISOString());
    await expect(
      r.beginSection({
        learnerId: LEARNER,
        runId: "run-1",
        sectionCode: "math",
      }),
    ).rejects.toBeInstanceOf(EngineRepoError);
  });

  it("finishSection is finish-once: a second finish cannot reopen (FR-2)", async () => {
    const { repo: r } = repo();
    await r.startRun({ learnerId: LEARNER, formId: "two-section" });
    await r.beginSection({
      learnerId: LEARNER,
      runId: "run-1",
      sectionCode: "english",
    });
    await r.upsertItems({ learnerId: LEARNER, items: [item()] });
    const first = await r.finishSection({
      learnerId: LEARNER,
      runId: "run-1",
      sectionCode: "english",
    });
    expect(first.status).toBe("submitted");
    expect(first.raw_correct).toBe(1);
    const second = await r.finishSection({
      learnerId: LEARNER,
      runId: "run-1",
      sectionCode: "english",
    });
    expect(second).toEqual(first);
    expect(second.status).toBe("submitted");
    await expect(
      r.beginSection({
        learnerId: LEARNER,
        runId: "run-1",
        sectionCode: "english",
      }),
    ).rejects.toBeInstanceOf(EngineRepoError);
  });
});
