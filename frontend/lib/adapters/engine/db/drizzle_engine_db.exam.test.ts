/**
 * W1-5 — drizzle exam store on L2 sqlite (FR-4 / FR-27 / FR-37 / FR-40).
 *
 * Same contract as InMemoryEngineDb: persist positional learnerId, upsert
 * via mergeExamDwell, begin keep-first, finish-once. `.onConflict` is the
 * write path on both dialects (shared helper).
 */

import { DatabaseSync, type SQLInputValue } from "node:sqlite";
import { drizzle } from "drizzle-orm/sqlite-proxy";
import { describe, expect, it } from "vitest";

import { mergeExamDwell } from "@/components/exam/exam_dwell_merge";
import type { ExamRun, ExamRunItem } from "../../../wire/exam_entities";
import { sqliteExamEngineDbFrom } from "./drizzle_engine_db";
import * as sqlite from "./schema.sqlite";

const SQLITE_EXAM_DDL = `
PRAGMA foreign_keys = ON;
CREATE TABLE exam_run (
  id text PRIMARY KEY NOT NULL,
  learner_id text NOT NULL,
  form_id text NOT NULL,
  created_at integer NOT NULL DEFAULT (unixepoch()),
  composite real
);
CREATE INDEX exam_run_learner_form_idx ON exam_run (learner_id, form_id);
CREATE TABLE exam_section_attempt (
  run_id text NOT NULL REFERENCES exam_run(id) ON DELETE CASCADE,
  section_code text NOT NULL,
  status text NOT NULL,
  started_at integer,
  finished_at integer,
  deadline_at integer,
  raw_correct integer,
  raw_scored_total integer,
  scale_score real,
  time_remaining_ms_at_submit integer,
  PRIMARY KEY (run_id, section_code)
);
CREATE TABLE exam_run_item (
  run_id text NOT NULL REFERENCES exam_run(id) ON DELETE CASCADE,
  section_code text NOT NULL,
  question_id text NOT NULL,
  ordinal integer NOT NULL,
  chosen_letter text,
  correct integer,
  dwell_ms integer NOT NULL DEFAULT 0,
  visits integer NOT NULL DEFAULT 0,
  answer_changes integer NOT NULL DEFAULT 0,
  first_answered_at integer,
  dwell_at_first_answer_ms integer,
  flagged_in_section integer NOT NULL DEFAULT 0,
  bookmarked integer NOT NULL DEFAULT 0,
  updated_at integer NOT NULL DEFAULT (unixepoch()),
  PRIMARY KEY (run_id, section_code, question_id)
);
CREATE INDEX exam_run_item_run_section_idx ON exam_run_item (run_id, section_code);
`;

function asSqlParams(params: unknown[]): SQLInputValue[] {
  return params as SQLInputValue[];
}

function execSqlite(
  raw: DatabaseSync,
  sql: string,
  params: unknown[],
  method: "run" | "all" | "values" | "get",
): { rows: unknown[] } {
  const bound = asSqlParams(params);
  if (method === "run") {
    raw.prepare(sql).run(...bound);
    return { rows: [] };
  }
  const stmt = raw.prepare(sql);
  if (method === "get") {
    const row = stmt.get(...bound);
    return { rows: row ? Object.values(row) : [] };
  }
  const rows = stmt.all(...bound);
  return { rows: rows.map((r) => Object.values(r)) };
}

function openSqliteExamDb() {
  const raw = new DatabaseSync(":memory:");
  raw.exec(SQLITE_EXAM_DDL);
  const db = drizzle(
    async (sql, params, method) => execSqlite(raw, sql, params, method),
    { schema: sqlite },
  );
  return sqliteExamEngineDbFrom(db);
}

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

async function startedDb() {
  const db = openSqliteExamDb();
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

describe("DrizzleEngineDb exam store — L2 sqlite (W1-5 / FR-4/27/37)", () => {
  it("persists positional learnerId, not run.learner_id", async () => {
    const db = openSqliteExamDb();
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

  it("merges dwell monotonic-max via mergeExamDwell (FR-4 / FR-39)", async () => {
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
    expect(merged).toBeDefined();
    if (merged == null) throw new Error("expected merged exam item");
    expect(merged).toEqual(mergeExamDwell(stored, incoming));
    expect(merged.dwell_ms).toBe(250);
    expect(merged.visits).toBe(3);
    expect(merged.answer_changes).toBe(2);
    expect(merged.first_answered_at).toBe("2026-09-02T00:00:01.000Z");
    expect(merged.dwell_at_first_answer_ms).toBe(80);
    expect(merged.chosen_letter).toBe("B");
  });

  it("begin keep-first: retry does not reset started_at or deadline (FR-37)", async () => {
    const db = openSqliteExamDb();
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
