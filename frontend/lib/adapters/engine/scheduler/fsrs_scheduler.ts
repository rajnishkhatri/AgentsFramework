/**
 * FsrsScheduler — the `Scheduler` adapter (ADR-0006 #5), the ONLY writer of
 * `skill_state` (engine spec FR-A2).
 *
 * SDK confinement (F-R2 / Rule A1): `ts-fsrs` is imported ONLY here. The FSRS
 * card type never escapes — `review()` returns a `wire/engine_entities`
 * `SkillState`, and `skill_state` columns (`fsrs_stability`, `fsrs_difficulty`,
 * `due_at`, `mastery`, `last_seen`) are the durable, vendor-neutral projection of
 * an FSRS card. A future swap to another spaced-repetition lib changes only this
 * file (Rule F3).
 *
 * @sdk ts-fsrs ^5.4.1
 *
 * Behavior:
 *   - `next()` reads `skill_state` for the learner; if EMPTY it seeds one default
 *     row per skill (mastery 0, due_at = now) so the first session is well-defined
 *     (FR-A7). It then picks the most-due, weakest skill (lowest mastery among
 *     `due_at <= now`, tie-broken by due_at) and asks `QuestionRepo` for a
 *     reviewed question for it (FR-A1). The reviewed gate is the repo's; the
 *     scheduler is subject-agnostic.
 *   - `review(attempt)` maps `attempt.correct` → an FSRS rating (Good / Again),
 *     advances the card from the prior `skill_state` (or a fresh card), and
 *     upserts the new `skill_state`. Deterministic given prior state + attempt +
 *     the injected clock.
 *
 * Mastery projection: FSRS has no 0..1 "mastery" — the UI needs one (Progress
 * bars, weakest-skill pick). We project `mastery = retrievability at review time`
 * (forgetting curve over stability), clamped to [0,1]. This keeps "weakest" and
 * "most due" consistent: a freshly-failed card has low stability → low mastery.
 */

import {
  createEmptyCard,
  FSRS,
  generatorParameters,
  Rating,
  type Card,
  type Grade,
} from "ts-fsrs";
import type { Scheduler } from "../../../ports/engine/scheduler";
import { EngineNotFoundError, SchedulerError } from "../../../ports/engine/errors";
import type {
  Attempt,
  NextItem,
  SkillState,
} from "../../../wire/engine_entities";
import type { EngineDb } from "../db/engine_db";
import type { QuestionRepo } from "../../../ports/engine/question_repo";

export type FsrsSchedulerDeps = {
  db: EngineDb;
  /** Used to resolve the chosen skill → a reviewed question (FR-A1). */
  questions: QuestionRepo;
  /** Injectable clock for deterministic tests; defaults to () => new Date(). */
  now?: () => Date;
};

export class FsrsScheduler implements Scheduler {
  private readonly db: EngineDb;
  private readonly questions: QuestionRepo;
  private readonly now: () => Date;
  private readonly fsrs: FSRS;

  constructor(deps: FsrsSchedulerDeps) {
    this.db = deps.db;
    this.questions = deps.questions;
    this.now = deps.now ?? (() => new Date());
    // Deterministic params (fuzz OFF so tests are reproducible — fuzz adds
    // randomness to the interval, which we never want on the verifier path).
    this.fsrs = new FSRS(generatorParameters({ enable_fuzz: false }));
  }

  async next(
    subject: string,
    learnerId: string,
    servedIds?: readonly string[],
  ): Promise<NextItem> {
    let states: SkillState[];
    try {
      states = await this.db.listSkillState(subject, learnerId);
      if (states.length === 0) {
        states = await this.seed(subject, learnerId);
      }
    } catch (err) {
      throw translate("next", err);
    }
    if (states.length === 0) {
      // No skills exist for the subject at all — nothing schedulable.
      throw new EngineNotFoundError(
        `no skills to schedule for subject '${subject}'`,
      );
    }

    const nowMs = this.now().getTime();
    // Most-due, weakest first: prefer due (due_at <= now), then lowest mastery,
    // then earliest due_at. Falls back to the globally weakest if none are due.
    const due = states.filter((s) => Date.parse(s.due_at) <= nowMs);
    // Copy before sorting: `states` may be a reference an EngineDb impl shares
    // (and `filter` aliases nothing when due is empty), so sort a fresh array.
    const pool = [...(due.length > 0 ? due : states)];
    pool.sort(
      (a, b) =>
        a.mastery - b.mastery ||
        Date.parse(a.due_at) - Date.parse(b.due_at) ||
        // Final deterministic tie-break: identical mastery + due_at (e.g. a
        // freshly seeded learner) must resolve to a stable skill regardless of
        // store row order (the pg seam's listSkillIds has no ORDER BY).
        a.skill_id.localeCompare(b.skill_id),
    );

    // S3 within-session no-repeat (FR-9/10/11): walk the weakest-first pool,
    // asking each skill for a reviewed question NOT in `servedIds`. The first
    // skill with an unserved item wins; when the weakest is exhausted we fall
    // through to the next (FR-10); when EVERY skill is exhausted we throw
    // not-found — end the session early, never repeat (FR-11). This is a pure
    // read walk: no `skill_state` write (FR-13 — `review()` is the sole writer).
    // Omitted/empty `servedIds` degenerates to the single-pick behaviour: the
    // weakest skill's `nextReviewed` is asked with no exclusion, exactly as before.
    //
    // The walk assumes the seeded-due invariant: a fresh session seeds every
    // skill `due_at = now` (FR-A7), so `pool` is ALL skills and exhaustion means
    // the learner's whole reviewed bank is served. A skill only leaves the due
    // set after its own `review()` pushes `due_at` forward — at which point
    // excluding it from the pool is correct (it was just reviewed, not stranded).
    for (const candidate of pool) {
      const question = await this.questions
        .nextReviewed(subject, candidate.skill_id, servedIds)
        .catch((err) => {
          throw translate("next", err);
        });
      if (question) {
        return { skill_id: candidate.skill_id, question_id: question.id };
      }
    }
    // Every skill in the pool is exhausted (no unserved reviewed item anywhere).
    throw new EngineNotFoundError(
      `no unserved reviewed question for learner '${learnerId}' (subject '${subject}')`,
    );
  }

  async review(attempt: Attempt): Promise<SkillState> {
    const reviewedAt = this.now();
    let prior: SkillState | null;
    try {
      // The attempt's skill: resolve via its question.
      const question = await this.questions.get(attempt.question_id);
      if (!question) {
        throw new EngineNotFoundError(
          `attempt references unknown question '${attempt.question_id}'`,
        );
      }
      const learnerId = await this.learnerIdForAttempt(attempt);
      prior = await this.db.getSkillState(
        attempt.subject,
        question.skill_id,
        learnerId,
      );

      const card = prior ? this.toCard(prior, reviewedAt) : createEmptyCard(reviewedAt);
      const rating: Grade = attempt.correct ? Rating.Good : Rating.Again;
      const next = this.fsrs.next(card, reviewedAt, rating);
      const updated = this.fromCard(
        next.card,
        attempt.subject,
        question.skill_id,
        learnerId,
        reviewedAt,
      );
      await this.db.upsertSkillState(updated); // the SOLE skill_state write
      return updated;
    } catch (err) {
      throw translate("review", err);
    }
  }

  // --- seeding (FR-A7) ---
  private async seed(subject: string, learnerId: string): Promise<SkillState[]> {
    const skillIds = await this.db.listSkillIds(subject);
    const nowIso = this.now().toISOString();
    const seeded: SkillState[] = skillIds.map((skill_id) => ({
      subject,
      skill_id,
      learner_id: learnerId,
      mastery: 0,
      last_seen: null,
      fsrs_stability: 0,
      fsrs_difficulty: 0,
      due_at: nowIso, // due immediately so the first session is well-defined
      fsrs_card: null, // no card yet — toCard falls back to the named columns (New)
    }));
    for (const s of seeded) await this.db.upsertSkillState(s);
    return seeded;
  }

  // --- FSRS <-> SkillState projection (the vendor boundary) ---
  /**
   * Reconstitute the FSRS card from prior state. The card's FULL state machine
   * (state/reps/lapses/learning_steps/elapsed_days/scheduled_days) must survive
   * across reviews — restoring only stability/difficulty/due would leave the
   * card in `New` forever, so `fsrs.next` would treat every review as the first
   * and the interval would never grow. We therefore round-trip the whole card
   * via the opaque `fsrs_card` snapshot, falling back to the named columns only
   * for a seeded/legacy row that predates the snapshot.
   */
  private toCard(state: SkillState, fallbackNow: Date): Card {
    const snapshot = this.cardFromSnapshot(state.fsrs_card);
    if (snapshot) return snapshot;

    // Fallback: no snapshot yet (seeded row or pre-snapshot data). Build from
    // the named columns; a fresh seed is correctly `New` here.
    const base = createEmptyCard(
      state.last_seen ? new Date(state.last_seen) : fallbackNow,
    );
    const card: Card = {
      ...base,
      stability: state.fsrs_stability,
      difficulty: state.fsrs_difficulty,
      due: new Date(state.due_at),
    };
    // `exactOptionalPropertyTypes`: include last_review only when present
    // (omit the key rather than assign undefined).
    if (state.last_seen) card.last_review = new Date(state.last_seen);
    return card;
  }

  /** Parse the opaque snapshot back into a Card (dates are ISO strings on the wire). */
  private cardFromSnapshot(snapshot: unknown): Card | null {
    if (!snapshot || typeof snapshot !== "object") return null;
    const s = snapshot as Record<string, unknown>;
    if (s.due == null || s.stability == null) return null;
    const card: Card = {
      due: new Date(s.due as string),
      stability: Number(s.stability),
      difficulty: Number(s.difficulty),
      elapsed_days: Number(s.elapsed_days ?? 0),
      scheduled_days: Number(s.scheduled_days ?? 0),
      reps: Number(s.reps ?? 0),
      lapses: Number(s.lapses ?? 0),
      learning_steps: Number(s.learning_steps ?? 0),
      state: Number(s.state ?? 0) as Card["state"],
    };
    if (s.last_review != null) card.last_review = new Date(s.last_review as string);
    return card;
  }

  /** Serialize a Card into the opaque snapshot (dates → ISO strings). */
  private cardToSnapshot(card: Card): Record<string, unknown> {
    const snapshot: Record<string, unknown> = {
      due: card.due.toISOString(),
      stability: card.stability,
      difficulty: card.difficulty,
      elapsed_days: card.elapsed_days,
      scheduled_days: card.scheduled_days,
      reps: card.reps,
      lapses: card.lapses,
      learning_steps: card.learning_steps,
      state: card.state,
    };
    if (card.last_review) snapshot.last_review = card.last_review.toISOString();
    return snapshot;
  }

  private fromCard(
    card: Card,
    subject: string,
    skillId: string,
    learnerId: string,
    reviewedAt: Date,
  ): SkillState {
    return {
      subject,
      skill_id: skillId,
      learner_id: learnerId,
      mastery: this.retrievability(card, reviewedAt),
      last_seen: reviewedAt.toISOString(),
      fsrs_stability: card.stability,
      fsrs_difficulty: card.difficulty,
      due_at: card.due.toISOString(),
      fsrs_card: this.cardToSnapshot(card),
    };
  }

  /** Project FSRS retrievability at `at` into a 0..1 mastery. */
  private retrievability(card: Card, at: Date): number {
    const r = this.fsrs.get_retrievability(card, at, false);
    const num = typeof r === "number" ? r : Number(r);
    if (!Number.isFinite(num)) return 0;
    return Math.min(1, Math.max(0, num));
  }

  /**
   * Resolve the learner for an attempt via its session. Kept here (not on the
   * Attempt row) because `attempt` is scoped by session, and skill_state is
   * keyed by learner.
   */
  private async learnerIdForAttempt(attempt: Attempt): Promise<string> {
    const session = await this.db.getSession(attempt.session_id);
    if (!session) {
      throw new EngineNotFoundError(
        `attempt references unknown session '${attempt.session_id}'`,
      );
    }
    return session.learner_id;
  }
}

function translate(op: string, err: unknown): SchedulerError {
  if (err instanceof SchedulerError || err instanceof EngineNotFoundError) {
    // Preserve not-found as-is so callers can distinguish 404 from 500.
    return err as SchedulerError;
  }
  const detail = err instanceof Error ? err.message : String(err);
  return new SchedulerError(`scheduler ${op} failed: ${detail}`);
}
