/**
 * L1 tests for FsrsScheduler (engine spec §8 scheduler.spec rows).
 *
 * The scheduler is the SOLE writer of skill_state (FR-A2) and owns seeding
 * (FR-A7). ts-fsrs is real (confined to the adapter); the clock is injected so
 * the FSRS math is deterministic. Run against InMemoryEngineDb + a real
 * DrizzleQuestionRepo over the same fake.
 *
 * Failure path first: no schedulable item → EngineNotFoundError, BEFORE the
 * seeding + pick + review paths.
 */

import { describe, expect, it } from "vitest";
import { InMemoryEngineDb } from "../db/in_memory_engine_db";
import { DrizzleQuestionRepo } from "../repos/drizzle_question_repo";
import { FsrsScheduler } from "./fsrs_scheduler";
import { EngineNotFoundError } from "../../../ports/engine/errors";
import type { Attempt, Question, Skill } from "../../../wire/engine_entities";

const NOW = new Date("2026-06-30T12:00:00Z");

function setup() {
  const db = new InMemoryEngineDb();
  const questions = new DrizzleQuestionRepo(db);
  const scheduler = new FsrsScheduler({ db, questions, now: () => NOW });
  return { db, questions, scheduler };
}

/** A scheduler over an existing db with a caller-supplied clock (for multi-review). */
function schedulerOver(db: InMemoryEngineDb, now: () => Date) {
  const questions = new DrizzleQuestionRepo(db);
  return new FsrsScheduler({ db, questions, now });
}

function skill(over: Partial<Skill> = {}): Skill {
  return {
    id: "s1",
    subject: "act-english",
    key: "punctuation",
    name: "Punctuation",
    share_of_test_pct: 13,
    accent_var: "",
    description: "",
    order: 1,
    ...over,
  };
}

function reviewedQuestion(over: Partial<Question> = {}): Question {
  return {
    id: "q1",
    subject: "act-english",
    skill_id: "s1",
    difficulty: 2,
    context_html: "",
    stem: "",
    choices: [{ letter: "A", label: "NO CHANGE", is_no_change: true }],
    answer_letter: "A",
    per_choice_rationale: {},
    why_correct_md: "",
    why_tempted_md: "",
    rule_md: "",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

describe("FsrsScheduler — failure path first", () => {
  it("next throws EngineNotFoundError when the subject has no skills", async () => {
    const { scheduler } = setup();
    await expect(scheduler.next("act-english", "alice")).rejects.toBeInstanceOf(
      EngineNotFoundError,
    );
  });

  it("next throws EngineNotFoundError when the chosen skill has no reviewed question", async () => {
    const { db, scheduler } = setup();
    db.seedSkills([skill()]);
    db.seedQuestions([reviewedQuestion({ reviewed: false })]); // unreviewed only
    await expect(scheduler.next("act-english", "alice")).rejects.toBeInstanceOf(
      EngineNotFoundError,
    );
  });
});

describe("FsrsScheduler — seeding (FR-A7) + pick (FR-A1) + sole writer (FR-A2)", () => {
  it("a brand-new learner is seeded one default state per skill, then served", async () => {
    const { db, scheduler } = setup();
    db.seedSkills([skill({ id: "s1" }), skill({ id: "s2", key: "rhetoric" })]);
    db.seedQuestions([
      reviewedQuestion({ id: "q1", skill_id: "s1" }),
      reviewedQuestion({ id: "q2", skill_id: "s2" }),
    ]);

    // No skill_state exists yet.
    expect(await db.listSkillState("act-english", "alice")).toHaveLength(0);

    const pick = await scheduler.next("act-english", "alice");

    // Seeding happened: one row per skill, mastery 0, due now.
    const seeded = await db.listSkillState("act-english", "alice");
    expect(seeded).toHaveLength(2);
    expect(seeded.every((s) => s.mastery === 0)).toBe(true);
    // A schedulable item was returned.
    expect(["s1", "s2"]).toContain(pick.skill_id);
    expect(["q1", "q2"]).toContain(pick.question_id);
  });

  it("review applies the FSRS update and is the only skill_state write (FR-A2)", async () => {
    const { db, scheduler } = setup();
    db.seedSkills([skill({ id: "s1" })]);
    db.seedQuestions([reviewedQuestion({ id: "q1", skill_id: "s1" })]);
    await db.insertSession({
      id: "sess1",
      subject: "act-english",
      learner_id: "alice",
      mode: "adaptive",
      skill_focus: null,
      started_at: NOW.toISOString(),
      ended_at: null,
      score_correct: 0,
      score_total: 0,
      target_count: null,
    });

    const attempt: Attempt = {
      id: "a1",
      subject: "act-english",
      session_id: "sess1",
      question_id: "q1",
      chosen_letter: "A",
      correct: true,
      elapsed_ms: 1000,
      used_hint: false,
      created_at: NOW.toISOString(),
    };

    const before = await db.getSkillState("act-english", "s1", "alice");
    expect(before).toBeNull();

    const state = await scheduler.review(attempt);
    expect(state.subject).toBe("act-english");
    expect(state.skill_id).toBe("s1");
    expect(state.learner_id).toBe("alice");
    expect(state.last_seen).toBe(NOW.toISOString());
    // A correct review advances the card → future due date, positive stability.
    expect(Date.parse(state.due_at)).toBeGreaterThan(NOW.getTime());
    expect(state.fsrs_stability).toBeGreaterThan(0);
    expect(state.mastery).toBeGreaterThanOrEqual(0);
    expect(state.mastery).toBeLessThanOrEqual(1);

    // It was persisted (the sole writer wrote it).
    const persisted = await db.getSkillState("act-english", "s1", "alice");
    expect(persisted).toEqual(state);
  });

  it("successive correct reviews grow the interval (the card state must advance, not reset)", async () => {
    const { db, scheduler } = setup();
    db.seedSkills([skill({ id: "s1" })]);
    db.seedQuestions([reviewedQuestion({ id: "q1", skill_id: "s1" })]);
    await db.insertSession({
      id: "sess1",
      subject: "act-english",
      learner_id: "alice",
      mode: "adaptive",
      skill_focus: null,
      started_at: NOW.toISOString(),
      ended_at: null,
      score_correct: 0,
      score_total: 0,
      target_count: null,
    });
    const attempt = (createdAt: Date): Attempt => ({
      id: "a",
      subject: "act-english",
      session_id: "sess1",
      question_id: "q1",
      chosen_letter: "A",
      correct: true,
      elapsed_ms: 1000,
      used_hint: false,
      created_at: createdAt.toISOString(),
    });

    // Review 1 at NOW.
    const s1 = await scheduler.review(attempt(NOW));
    const interval1 = Date.parse(s1.due_at) - NOW.getTime();

    // Review 2 AT the due time. The card must advance out of the learning step
    // (New/Learning → Review), so the next interval is dramatically larger. A
    // card that reset to New each review would just re-schedule the same ~10-min
    // learning step (interval2 === interval1) — the original bug.
    const due1 = new Date(s1.due_at);
    const s2 = await schedulerOver(db, () => due1).review(attempt(due1));
    const interval2 = Date.parse(s2.due_at) - due1.getTime();

    // Review 3: now in the Review state, stability (and the interval) grows.
    const due2 = new Date(s2.due_at);
    const s3 = await schedulerOver(db, () => due2).review(attempt(due2));
    const interval3 = Date.parse(s3.due_at) - due2.getTime();

    expect(s1.fsrs_stability).toBeGreaterThan(0);
    // Graduating the learning step expands the interval by orders of magnitude.
    expect(interval2).toBeGreaterThan(interval1);
    // Continued correct reviews keep growing both stability and the interval —
    // proof the card's state machine is being carried across reviews.
    expect(s3.fsrs_stability).toBeGreaterThan(s1.fsrs_stability);
    expect(interval3).toBeGreaterThan(interval2);
  });

  it("an incorrect review schedules sooner than a correct one (deterministic)", async () => {
    const mk = () => {
      const { db, scheduler } = setup();
      db.seedSkills([skill({ id: "s1" })]);
      db.seedQuestions([reviewedQuestion({ id: "q1", skill_id: "s1" })]);
      void db.insertSession({
        id: "sess1",
        subject: "act-english",
        learner_id: "alice",
        mode: "adaptive",
        skill_focus: null,
        started_at: NOW.toISOString(),
        ended_at: null,
        score_correct: 0,
        score_total: 0,
        target_count: null,
      });
      return scheduler;
    };
    const base: Attempt = {
      id: "a1",
      subject: "act-english",
      session_id: "sess1",
      question_id: "q1",
      chosen_letter: "A",
      correct: true,
      elapsed_ms: 1000,
      used_hint: false,
      created_at: NOW.toISOString(),
    };
    const correct = await mk().review({ ...base, correct: true });
    const wrong = await mk().review({ ...base, correct: false });
    expect(Date.parse(wrong.due_at)).toBeLessThan(Date.parse(correct.due_at));
  });
});

// --- S3: within-session no-repeat via servedIds (FR-9/10/11/13) ---

/** A default skill_state row so a learner is pre-seeded (no seeding upsert). */
function seededState(over: Partial<import("../../../wire/engine_entities").SkillState> = {}) {
  return {
    subject: "act-english",
    skill_id: "s1",
    learner_id: "alice",
    mastery: 0.1,
    last_seen: null,
    fsrs_stability: 0,
    fsrs_difficulty: 0,
    due_at: NOW.toISOString(), // due now → in the pool
    fsrs_card: null,
    ...over,
  };
}

describe("FsrsScheduler — servedIds no-repeat (FR-9/10/11/13)", () => {
  it("next never returns a served question id (FR-9)", async () => {
    const { db, scheduler } = setup();
    db.seedSkills([skill({ id: "s1" })]);
    db.seedSkillStates([seededState({ skill_id: "s1" })]);
    db.seedQuestions([
      reviewedQuestion({ id: "q1", skill_id: "s1", difficulty: 1 }),
      reviewedQuestion({ id: "q2", skill_id: "s1", difficulty: 2 }),
    ]);
    const pick = await scheduler.next("act-english", "alice", ["q1"]);
    expect(pick.question_id).toBe("q2"); // q1 served → the next item for the skill
  });

  it("when the weakest skill is exhausted, falls through to the next-weakest (FR-10)", async () => {
    const { db, scheduler } = setup();
    db.seedSkills([skill({ id: "s1" }), skill({ id: "s2", key: "rhetoric" })]);
    // s1 is weaker (lower mastery) so it is chosen first; its only item is served.
    db.seedSkillStates([
      seededState({ skill_id: "s1", mastery: 0.1 }),
      seededState({ skill_id: "s2", mastery: 0.5 }),
    ]);
    db.seedQuestions([
      reviewedQuestion({ id: "q-s1", skill_id: "s1" }),
      reviewedQuestion({ id: "q-s2", skill_id: "s2" }),
    ]);
    const pick = await scheduler.next("act-english", "alice", ["q-s1"]);
    // s1 exhausted (its only item served) → fall through to s2, not a repeat/throw.
    expect(pick.skill_id).toBe("s2");
    expect(pick.question_id).toBe("q-s2");
  });

  it("throws EngineNotFoundError when every skill's items are all served (FR-11)", async () => {
    const { db, scheduler } = setup();
    db.seedSkills([skill({ id: "s1" }), skill({ id: "s2", key: "rhetoric" })]);
    db.seedSkillStates([
      seededState({ skill_id: "s1", mastery: 0.1 }),
      seededState({ skill_id: "s2", mastery: 0.5 }),
    ]);
    db.seedQuestions([
      reviewedQuestion({ id: "q-s1", skill_id: "s1" }),
      reviewedQuestion({ id: "q-s2", skill_id: "s2" }),
    ]);
    // Both (the whole bank for this learner) already served → end early, no repeat.
    await expect(
      scheduler.next("act-english", "alice", ["q-s1", "q-s2"]),
    ).rejects.toBeInstanceOf(EngineNotFoundError);
  });

  it("next(servedIds) performs NO skill_state write — the served set is read-only (FR-13)", async () => {
    const { db } = setup();
    db.seedSkills([skill({ id: "s1" })]);
    db.seedSkillStates([seededState({ skill_id: "s1" })]); // pre-seeded → no seeding upsert
    db.seedQuestions([
      reviewedQuestion({ id: "q1", skill_id: "s1", difficulty: 1 }),
      reviewedQuestion({ id: "q2", skill_id: "s1", difficulty: 2 }),
    ]);
    // Count upserts through a pass-through spy on the fake.
    let upserts = 0;
    const original = db.upsertSkillState.bind(db);
    db.upsertSkillState = async (s) => {
      upserts += 1;
      return original(s);
    };
    const scheduler = new FsrsScheduler({
      db,
      questions: new DrizzleQuestionRepo(db),
      now: () => NOW,
    });
    await scheduler.next("act-english", "alice", ["q1"]);
    expect(upserts).toBe(0); // exclusion is a pure read path; review() is the sole writer
  });
});
