/**
 * B-8 — getExamRun review reveal (FR-P2-9).
 *
 * Correct-answer + rationale fields are merged from keys only for
 * finished attempts. In-progress payloads stay stripped.
 */

import { describe, expect, it } from "vitest";

import { ANSWER_BEARING_FIELDS } from "@/components/exam/exam_key_posture";
import { FAKE_OFFICIAL_FORM } from "../exam_forms/fixtures/fake_official_form";
import { ExactLetterGrader } from "../grader/exact_letter_grader";
import { finishExamSectionServer } from "../exam_server_grade";
import { InMemoryEngineDb } from "./in_memory_engine_db";
import type { ExamRunItem } from "../../../wire/exam_entities";

const LEARNER = "learner-1";
const NOW = "2026-09-03T12:00:00.000Z";

function item(questionId: string, chosen: string): ExamRunItem {
  return {
    run_id: "run-1",
    section_code: "english",
    question_id: questionId,
    ordinal: 0,
    chosen_letter: chosen,
    correct: null,
    dwell_ms: 10,
    visits: 1,
    answer_changes: 0,
    first_answered_at: NOW,
    dwell_at_first_answer_ms: 10,
    flagged_in_section: false,
    bookmarked: false,
    updated_at: NOW,
  };
}

describe("getExamRun review reveal (B-8 / FR-P2-9)", () => {
  it("in-progress payload has no answer-bearing fields", async () => {
    const db = new InMemoryEngineDb();
    db.seedExamForm(FAKE_OFFICIAL_FORM);
    await db.insertExamRun(LEARNER, {
      id: "run-1",
      learner_id: LEARNER,
      form_id: FAKE_OFFICIAL_FORM.id,
      created_at: NOW,
      composite: null,
    });
    await db.beginExamSection(
      LEARNER,
      "run-1",
      "english",
      NOW,
      "2026-09-03T12:10:00.000Z",
    );
    const q = FAKE_OFFICIAL_FORM.sections[0]!.questions[0]!;
    await db.upsertExamRunItems(LEARNER, "run-1", "english", [
      item(q.id, q.answer_letter),
    ]);

    const detail = await db.getExamRun(LEARNER, "run-1");
    expect(detail).not.toBeNull();
    expect(detail!.review ?? []).toEqual([]);
    const raw = JSON.stringify(detail);
    for (const field of ANSWER_BEARING_FIELDS) {
      expect(raw).not.toContain(`"${field}"`);
    }
  });

  it("finished payload includes correct-answer + rationale from keys", async () => {
    const db = new InMemoryEngineDb();
    db.seedExamForm(FAKE_OFFICIAL_FORM);
    await db.insertExamRun(LEARNER, {
      id: "run-1",
      learner_id: LEARNER,
      form_id: FAKE_OFFICIAL_FORM.id,
      created_at: NOW,
      composite: null,
    });
    await db.beginExamSection(
      LEARNER,
      "run-1",
      "english",
      NOW,
      "2026-09-03T12:10:00.000Z",
    );
    const q = FAKE_OFFICIAL_FORM.sections[0]!.questions[0]!;
    await db.upsertExamRunItems(LEARNER, "run-1", "english", [
      item(q.id, q.answer_letter),
    ]);
    await finishExamSectionServer(
      db,
      new ExactLetterGrader(),
      LEARNER,
      "run-1",
      "english",
      "submitted",
      { raw_correct: 0, raw_scored_total: 0, scale_score: null },
      0,
    );

    const detail = await db.getExamRun(LEARNER, "run-1");
    expect(detail).not.toBeNull();
    const reveal = detail!.review ?? [];
    expect(reveal.length).toBeGreaterThan(0);
    const hit = reveal.find((r) => r.question_id === q.id);
    expect(hit).toBeDefined();
    expect(hit!.answer_letter).toBe(q.answer_letter);
    expect(hit!.why_correct_md).toBe(q.why_correct_md);
    expect(hit!.per_choice_rationale).toEqual(q.per_choice_rationale);
  });
});
