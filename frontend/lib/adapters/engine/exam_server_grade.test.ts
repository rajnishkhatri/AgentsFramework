/**
 * B-4 — server-side grade-on-finish for asset-served forms (FR-P2-5/6).
 */

import { describe, expect, it } from "vitest";

import { ANSWER_BEARING_FIELDS } from "@/components/exam/exam_key_posture";
import { FAKE_OFFICIAL_FORM } from "./exam_forms/fixtures/fake_official_form";
import { ExactLetterGrader } from "./grader/exact_letter_grader";
import { InMemoryEngineDb } from "./db/in_memory_engine_db";
import { getExamForm } from "./exam_forms";
import { extractExamFormKeys, stripExamFormForClient } from "./exam_form_load";
import type { ExamRunItem } from "../../wire/exam_entities";
import {
  finishExamSectionServer,
  gradeAssetServedSection,
} from "./exam_server_grade";

const LEARNER = "learner-1";
const NOW = "2026-09-03T12:00:00.000Z";

function item(
  questionId: string,
  chosen: string,
  over: Partial<ExamRunItem> = {},
): ExamRunItem {
  return {
    run_id: "run-1",
    section_code: "english",
    question_id: questionId,
    ordinal: 0,
    chosen_letter: chosen,
    correct: true,
    dwell_ms: 10,
    visits: 1,
    answer_changes: 0,
    first_answered_at: NOW,
    dwell_at_first_answer_ms: 10,
    flagged_in_section: false,
    bookmarked: false,
    updated_at: NOW,
    ...over,
  };
}

describe("gradeAssetServedSection (B-4 / FR-P2-6)", () => {
  it("grades from keys, ignoring client-supplied correct", () => {
    const form = stripExamFormForClient(FAKE_OFFICIAL_FORM);
    const keys = extractExamFormKeys(FAKE_OFFICIAL_FORM);
    const english = FAKE_OFFICIAL_FORM.sections[0]!;
    const items = english.questions.map((q, i) =>
      item(q.id, i === 0 ? q.answer_letter : "A", {
        ordinal: i,
        correct: true,
      }),
    );
    const score = gradeAssetServedSection(
      form,
      keys,
      "english",
      items,
      new ExactLetterGrader(),
    );
    expect(score.grades[0]!.correct).toBe(true);
    expect(score.grades[1]!.correct).toBe(false);
    expect(score.raw_correct).toBe(1);
    expect(score.raw_scored_total).toBe(1);
  });
});

describe("finishExamSectionServer (B-4 / FR-P2-5)", () => {
  it("asset-served: ignores client grades and persists the server score", async () => {
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
    const english = FAKE_OFFICIAL_FORM.sections[0]!;
    const items = english.questions.map((q, i) =>
      item(q.id, q.answer_letter, { ordinal: i, correct: false }),
    );
    await db.upsertExamRunItems(LEARNER, "run-1", "english", items);

    const pre = await db.getExamFormForClient(LEARNER, FAKE_OFFICIAL_FORM.id);
    const raw = JSON.stringify(pre);
    for (const field of ANSWER_BEARING_FIELDS) {
      expect(raw).not.toContain(`"${field}"`);
    }

    const finished = await finishExamSectionServer(
      db,
      new ExactLetterGrader(),
      LEARNER,
      "run-1",
      "english",
      "submitted",
      { raw_correct: 99, raw_scored_total: 99, scale_score: 36 },
      1000,
    );
    expect(finished.status).toBe("submitted");
    expect(finished.raw_correct).toBe(1);
    expect(finished.raw_scored_total).toBe(1);
    expect(finished.scale_score).not.toBe(36);

    const detail = await db.getExamRun(LEARNER, "run-1");
    expect(detail!.items.every((i) => i.correct === true)).toBe(true);
  });

  it("client-bundled Test-01 finish persists the supplied grades unchanged", async () => {
    const db = new InMemoryEngineDb();
    const form = getExamForm("test01-english");
    await db.insertExamRun(LEARNER, {
      id: "run-1",
      learner_id: LEARNER,
      form_id: form.id,
      created_at: NOW,
      composite: null,
    });
    await db.beginExamSection(
      LEARNER,
      "run-1",
      "english",
      NOW,
      "2026-09-03T12:45:00.000Z",
    );
    const finished = await finishExamSectionServer(
      db,
      new ExactLetterGrader(),
      LEARNER,
      "run-1",
      "english",
      "submitted",
      { raw_correct: 3, raw_scored_total: 5, scale_score: null },
      0,
    );
    expect(finished.raw_correct).toBe(3);
    expect(finished.raw_scored_total).toBe(5);
    expect(finished.scale_score).toBeNull();
  });
});
