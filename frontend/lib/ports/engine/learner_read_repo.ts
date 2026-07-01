/** LearnerReadRepo port (ADR-0011) — read-only skill_state for the UI. */

import type { SkillState } from "../../wire/engine_entities";

/**
 * LearnerReadRepo — the read-only view of a learner's `skill_state` (ADR-0011).
 *
 * Dashboard mastery (FR-C3) and the Summary mastery delta (FR-G1) need to READ
 * per-skill mastery, but no ADR-0006 port surfaced it and UI code may not touch
 * the `EngineDb` adapter seam (C2/F-R1). This is the smallest correct unblock:
 * one read method over the reads that already exist on `EngineDb` + the in-memory
 * fake.
 *
 * Behavioral contract:
 *   1. READ-ONLY. This port has no write method — the `Scheduler` stays the sole
 *      writer of `skill_state` (engine spec FR-A2). The adapter is typed against
 *      the `ReadableEngineDb` projection so a write is not even reachable
 *      (compiler-enforced; ADR-0011 §Decision).
 *   2. `listSkillState(subject, learner)` returns every persisted `skill_state`
 *      row for the learner — one per skill they have seen. A brand-new learner
 *      (or a skill never practised) has NO row; the caller/translator maps the
 *      absence to 0% (`bucket_card_vm` null→0%), never fabricates one here.
 *   3. Ordering is not guaranteed; callers key by `skill_id`.
 *   4. Returns `wire/engine_entities` shapes only — no SDK type escapes (F-R8).
 *
 * @throws EngineRepoError on a persistence failure.
 */
export interface LearnerReadRepo {
  /** All `skill_state` rows for a learner (read-only; keyed by skill downstream). */
  listSkillState(subject: string, learnerId: string): Promise<SkillState[]>;
}
