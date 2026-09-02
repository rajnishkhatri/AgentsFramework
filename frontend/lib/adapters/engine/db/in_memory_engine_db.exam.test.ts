/**
 * W1-4 — InMemoryEngineDb exam store (FR-4 / FR-27 / FR-37).
 *
 * L2: idempotent-once + monotonic-max upsert via exam_dwell_merge,
 * finish-once, begin keep-first. Persist positional learnerId, not
 * run.learner_id (W1-3).
 */

import { describe, expect, it } from "vitest";

import { mergeExamDwell } from "@/components/exam/exam_dwell_merge";
import type { ExamRun, ExamRunItem } from "../../../wire/exam_entities";
import { InMemoryEngineDb } from "./in_memory_engine_db";

function run(over: Partial<ExamRun> = {}): ExamRun {
  return {
    id: "run-1",
    learner_id: "spoofed-learner",
    form_id: "test01-english",
    created_at: "2026-09-02T00:00:00.000Z",
    composite: null,
    ...over,
  };
}

function item(over: Partial<ExamRunItem> = {}): ExamRunItem {
  return {
    run_id: "run-1",
    section_code: "english",
    question_id: "q-1",
    ordinal: 1,
    chosen_letter: "A",
    correct: null,
    dwell_ms: 100,
    visits: 1,
    answer_changes: 0,
    first_answered_at: "2026-09-02T00:00:01.000Z",
    dwell_at_first_answer_ms: 80,
    flagged_in_section: false,
    bookmarked: false,
    updated_at: "2026-09-02T00:00:02.000Z",
    ...over,
  };
}

async function startedDb(): Promise<InMemoryEngineDb> {
  const db = new InMemoryEngineDb();
  await db.insertExamRun("claim-learner", run());
  await db.beginExamSection(
    "claim-learner",
    "run-1",
    "english",
    "2026-09-02T00:00:00.000Z",
    "2026-09-02T00:45:00.000Z",
  );
  return db;
}

describe("InMemoryEngineDb exam store (W1-4 / FR-4/27/37)", () => {
  it("persists positional learnerId, not run.learner_id", async () => {
    const db = new InMemoryEngineDb();
    await db.insertExamRun("claim-learner", run({ learner_id: "spoofed-learner" }));
    const owned = await db.getExamRun("claim-learner", "run-1");
    expect(owned?.run.learner_id).toBe("claim-learner");
    expect(await db.getExamRun("spoofed-learner", "run-1")).toBeNull();
  });

  it("applies a duplicate item upsert once (FR-4 idempotent-once)", async () => {
    const db = await startedDb();
    const write = item();
    await db.upsertExamRunItems("claim-learner", "run-1", "english", [write]);
    await db.upsertExamRunItems("claim-learner", "run-1", "english", [write]);
    const items = await db.listExamRunItemsByLearner("claim-learner");
    expect(items).toHaveLength(1);
    expect(items[0]).toEqual(write);
  });

  it("merges dwell monotonic-max and keep-first first-answer (FR-4)", async () => {
    const db = await startedDb();
    const stored = item({
      dwell_ms: 250,
      visits: 3,
      answer_changes: 2,
      first_answered_at: "2026-09-02T00:00:01.000Z",
      dwell_at_first_answer_ms: 80,
      chosen_letter: "A",
    });
    const incoming = item({
      dwell_ms: 100,
      visits: 1,
      answer_changes: 0,
      first_answered_at: "2026-09-02T00:00:08.000Z",
      dwell_at_first_answer_ms: 400,
      chosen_letter: "B",
      updated_at: "2026-09-02T00:00:09.000Z",
    });
    await db.upsertExamRunItems("claim-learner", "run-1", "english", [stored]);
    await db.upsertExamRunItems("claim-learner", "run-1", "english", [incoming]);
    const [merged] = await db.listExamRunItemsByLearner("claim-learner");
    if (!merged) throw new Error("expected a merged exam-run item");
    expect(merged).toEqual(mergeExamDwell(stored, incoming));
    expect(merged.dwell_ms).toBe(250);
    expect(merged.visits).toBe(3);
    expect(merged.answer_changes).toBe(2);
    expect(merged.first_answered_at).toBe("2026-09-02T00:00:01.000Z");
    expect(merged.dwell_at_first_answer_ms).toBe(80);
    expect(merged.chosen_letter).toBe("B");
  });

  it("begin keep-first: retry does not reset started_at or deadline (FR-37)", async () => {
    const db = new InMemoryEngineDb();
    await db.insertExamRun("claim-learner", run());
    const first = await db.beginExamSection(
      "claim-learner",
      "run-1",
      "english",
      "2026-09-02T00:00:00.000Z",
      "2026-09-02T00:45:00.000Z",
    );
    const retry = await db.beginExamSection(
      "claim-learner",
      "run-1",
      "english",
      "2026-09-02T00:10:00.000Z",
      "2026-09-02T00:55:00.000Z",
    );
    expect(retry.started_at).toBe(first.started_at);
    expect(retry.deadline_at).toBe(first.deadline_at);
    expect(retry.started_at).toBe("2026-09-02T00:00:00.000Z");
    expect(retry.deadline_at).toBe("2026-09-02T00:45:00.000Z");
  });

  it("finish-once: second finish returns stored grades (FR-27)", async () => {
    const db = await startedDb();
    const first = await db.finishExamSection(
      "claim-learner",
      "run-1",
      "english",
      "submitted",
      { raw_correct: 10, raw_scored_total: 24, scale_score: 32 },
      12000,
    );
    const second = await db.finishExamSection(
      "claim-learner",
      "run-1",
      "english",
      "expired",
      { raw_correct: 0, raw_scored_total: 1, scale_score: null },
      0,
    );
    expect(second).toEqual(first);
    expect(second.status).toBe("submitted");
    expect(second.raw_correct).toBe(10);
    expect(second.raw_scored_total).toBe(24);
    expect(second.scale_score).toBe(32);
    expect(second.time_remaining_ms_at_submit).toBe(12000);
  });
});
