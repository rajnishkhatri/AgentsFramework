/**
 * W1-5 / FR-40 (R8) — two-device concurrency against real Postgres.
 *
 * env-gated: DATABASE_URL. Skip is explicit (not silent) when the env cannot
 * run Postgres. CI with a live DATABASE_URL must execute this.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { Pool } from "pg";

import { mergeExamDwell } from "@/components/exam/exam_dwell_merge";
import type { ExamRun, ExamRunItem } from "../../../wire/exam_entities";
import { pgEngineDb } from "./drizzle_engine_db";
import { toNodePgConnectionString } from "../../db/node_pg_url";

const DATABASE_URL = process.env.DATABASE_URL?.trim() ?? "";
const gated = DATABASE_URL === "";

function run(over: Partial<ExamRun> = {}): ExamRun {
  return {
    id: `run-pg-${crypto.randomUUID()}`,
    learner_id: "spoofed-learner",
    form_id: "test01-english",
    created_at: "2026-09-02T00:00:00.000Z",
    composite: null,
    ...over,
  };
}

function item(runId: string, over: Partial<ExamRunItem> = {}): ExamRunItem {
  return {
    run_id: runId,
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

async function ensureExamTables(url: string): Promise<void> {
  const sqlPath = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../../../../drizzle/0005_exam_runs.sql",
  );
  const sql = readFileSync(sqlPath, "utf8");
  const pool = new Pool({ connectionString: toNodePgConnectionString(url) });
  try {
    await pool.query(sql);
  } finally {
    await pool.end();
  }
}

const describePg = gated ? describe.skip : describe;

describePg(
  "env-gated: DATABASE_URL — drizzle exam store real-Postgres two-device (W1-5 / FR-40 R8)",
  () => {
    it("two concurrent device upserts keep one row and monotonic-max dwell", async () => {
      await ensureExamTables(DATABASE_URL);
      const seed = run();
      const deviceA = pgEngineDb(DATABASE_URL);
      const deviceB = pgEngineDb(DATABASE_URL);
      await deviceA.insertExamRun("claim-learner", seed);
      await deviceA.beginExamSection(
        "claim-learner",
        seed.id,
        "english",
        "2026-09-02T00:00:00.000Z",
        "2026-09-02T00:45:00.000Z",
      );
      const stored = item(seed.id, {
        dwell_ms: 250,
        visits: 3,
        answer_changes: 2,
        first_answered_at: "2026-09-02T00:00:01.000Z",
        dwell_at_first_answer_ms: 80,
        chosen_letter: "A",
      });
      const incoming = item(seed.id, {
        dwell_ms: 100,
        visits: 1,
        answer_changes: 0,
        first_answered_at: "2026-09-02T00:00:08.000Z",
        dwell_at_first_answer_ms: 400,
        chosen_letter: "B",
        updated_at: "2026-09-02T00:00:09.000Z",
      });
      await Promise.all([
        deviceA.upsertExamRunItems("claim-learner", seed.id, "english", [stored]),
        deviceB.upsertExamRunItems("claim-learner", seed.id, "english", [incoming]),
      ]);
      const items = await deviceA.listExamRunItemsByLearner("claim-learner");
      const row = items.find((i) => i.run_id === seed.id && i.question_id === "q-1");
      expect(row).toBeDefined();
      expect(items.filter((i) => i.run_id === seed.id)).toHaveLength(1);
      expect(row!.dwell_ms).toBe(250);
      expect(row!.visits).toBe(3);
      expect(row!.answer_changes).toBe(2);
      // Last-writer-wins for chosen_letter; keep-first for first-answer
      // depends on which device committed first — both merge orders are
      // mergeExamDwell of the two payloads.
      const either = [mergeExamDwell(stored, incoming), mergeExamDwell(incoming, stored)];
      expect(either.some((m) => m.dwell_ms === row!.dwell_ms)).toBe(true);
    });
  },
);
