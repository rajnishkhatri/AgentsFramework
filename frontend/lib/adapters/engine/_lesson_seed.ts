/**
 * Hand-authored lesson seed for ONE skill (E1a / ADR-0028 / FR-2).
 *
 * Non-essential commas under the Punctuation bucket (`s-punc`). Copy is
 * human-leak-checked against the E1a design reference — no answer letter is
 * named in teaching prose; `completion_try.choices[].correct` is the only
 * gradable flag and stays local to the inert interactive (D3).
 *
 * Provenance: `generated_from: "hand:<author>@<date>"` — earned by authoring +
 * leak-check, gated by `test_tutorial_provenance_confinement.py` (scans the
 * shared JSON under `seed_sources/tutorials.json`).
 *
 * T R.8 / FR-G1: rows live in ``seed_sources/tutorials.json`` (shared with
 * ``scripts/emit_engine_seed_sql.py``) so browser and Postgres cannot drift.
 *
 * WHY THE `_` PREFIX. Dev/fixture module (same posture as `_hint_bank.ts`);
 * skipped by the adapter-conformance PAIRS scan.
 */

import type { Tutorial } from "../../wire/engine_entities";
import type { InMemoryEngineDb } from "./db/in_memory_engine_db";
import tutorialsJson from "./seed_sources/tutorials.json";

export const LESSON_SEED: readonly Tutorial[] =
  tutorialsJson as readonly Tutorial[];

/** Seed the in-memory engine with the authored lesson row(s). */
export function seedLessonContent(db: InMemoryEngineDb): void {
  for (const t of LESSON_SEED) {
    db.seedTutorial(t);
  }
}
