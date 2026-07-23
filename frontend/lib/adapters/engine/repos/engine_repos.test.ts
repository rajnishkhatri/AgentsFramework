/**
 * L1/L2 conformance + behavioral tests for the Drizzle engine repo adapters,
 * run against the `InMemoryEngineDb` behavioral fake (engine spec §8 rows).
 *
 * The repos depend only on the narrow `EngineDb` port, so this fake exercises
 * the full repo logic offline. The SAME behaviors the live `drizzleEngineDb`
 * seam must reproduce are asserted here (the seam is `tsc`-checked against the
 * real schemas; a live DB integration test is the §8.2 follow-up).
 *
 * Failure paths first (TAP-4): reviewed gate denies unreviewed, rejecting db →
 * typed error, not-found → typed error — BEFORE the happy paths.
 */

import { describe, expect, it } from "vitest";
import { InMemoryEngineDb } from "../db/in_memory_engine_db";
import type { EngineDb } from "../db/engine_db";
import { DrizzleSkillTaxonomy } from "./drizzle_skill_taxonomy";
import { DrizzleQuestionRepo } from "./drizzle_question_repo";
import { DrizzleAttemptRepo } from "./drizzle_attempt_repo";
import { DrizzleSessionRepo } from "./drizzle_session_repo";
import { DrizzleContentRepo } from "./drizzle_content_repo";
import { DrizzleLearnerReadRepo } from "./drizzle_learner_read_repo";
import {
  EngineNotFoundError,
  EngineRepoError,
} from "../../../ports/engine/errors";
import type { Question, Skill, SkillState } from "../../../wire/engine_entities";

function skill(over: Partial<Skill> = {}): Skill {
  return {
    id: "s-punct",
    subject: "act-english",
    key: "punctuation",
    name: "Punctuation",
    share_of_test_pct: 13,
    accent_var: "--accent-punct",
    description: "",
    order: 1,
    ...over,
  };
}

function question(over: Partial<Question> = {}): Question {
  return {
    id: "q1",
    subject: "act-english",
    skill_id: "s-punct",
    difficulty: 2,
    context_html: "x",
    stem: "y",
    choices: [{ letter: "A", label: "NO CHANGE", is_no_change: true }],
    answer_letter: "A",
    per_choice_rationale: {},
    why_correct_md: "",
    why_tempted_md: "",
    rule_md: "",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

/** A db that rejects every call — proves error translation (A5). */
function rejectingDb(): EngineDb {
  const boom = () => Promise.reject(new Error("ECONNRESET vendor noise"));
  return new Proxy({} as EngineDb, { get: () => boom });
}

// --- SkillTaxonomy -------------------------------------------------------

describe("DrizzleSkillTaxonomy — failure paths first", () => {
  it("get() throws EngineNotFoundError for an unknown key", async () => {
    const repo = new DrizzleSkillTaxonomy(new InMemoryEngineDb());
    await expect(repo.get("act-english", "nope")).rejects.toBeInstanceOf(
      EngineNotFoundError,
    );
  });

  it("translates a db rejection to EngineRepoError (no vendor type escapes)", async () => {
    const repo = new DrizzleSkillTaxonomy(rejectingDb());
    await expect(repo.list("act-english")).rejects.toBeInstanceOf(EngineRepoError);
  });
});

describe("DrizzleSkillTaxonomy — read paths", () => {
  it("list() is subject-scoped and ordered by display order; read-only (no mastery)", async () => {
    const db = new InMemoryEngineDb();
    db.seedSkills([
      skill({ id: "s2", key: "rhetoric", name: "Rhetoric", order: 2 }),
      skill({ id: "s1", key: "punctuation", name: "Punctuation", order: 1 }),
      skill({ id: "sX", subject: "algebra-i", key: "linear", order: 1 }),
    ]);
    const repo = new DrizzleSkillTaxonomy(db);
    const out = await repo.list("act-english");
    expect(out.map((s) => s.key)).toEqual(["punctuation", "rhetoric"]); // ordered, no algebra
    expect(out[0]).not.toHaveProperty("mastery"); // read-only taxonomy
  });
});

// --- QuestionRepo (the reviewed gate) ------------------------------------

describe("DrizzleQuestionRepo — the reviewed gate (FR-B*)", () => {
  it("nextReviewed NEVER returns an unreviewed item (the hard invariant)", async () => {
    const db = new InMemoryEngineDb();
    db.seedQuestions([
      question({ id: "u1", reviewed: false, difficulty: 1 }), // unreviewed, lowest difficulty
      question({ id: "r1", reviewed: true, difficulty: 5 }),
    ]);
    const repo = new DrizzleQuestionRepo(db);
    const got = await repo.nextReviewed("act-english", "s-punct");
    expect(got).not.toBeNull();
    expect(got!.id).toBe("r1"); // the reviewed one, even though u1 is "easier"
    expect(got!.reviewed).toBe(true);
  });

  it("nextReviewed returns null (not throw) when nothing reviewed exists", async () => {
    const db = new InMemoryEngineDb();
    db.seedQuestions([question({ id: "u1", reviewed: false })]);
    const repo = new DrizzleQuestionRepo(db);
    expect(await repo.nextReviewed("act-english", "s-punct")).toBeNull();
  });

  it("get(id) MAY return an unreviewed row (non-learner path)", async () => {
    const db = new InMemoryEngineDb();
    db.seedQuestions([question({ id: "u1", reviewed: false })]);
    const repo = new DrizzleQuestionRepo(db);
    const got = await repo.get("u1");
    expect(got!.reviewed).toBe(false);
  });

  // --- S3: excludeIds served-set filter (FR-9/FR-11/FR-12) ---

  it("nextReviewed skips an excluded id and returns the next candidate (FR-9)", async () => {
    const db = new InMemoryEngineDb();
    db.seedQuestions([
      question({ id: "q1", reviewed: true, difficulty: 1 }), // would win by difficulty
      question({ id: "q2", reviewed: true, difficulty: 2 }),
    ]);
    const repo = new DrizzleQuestionRepo(db);
    const got = await repo.nextReviewed("act-english", "s-punct", ["q1"]);
    expect(got!.id).toBe("q2"); // q1 excluded → next-easiest reviewed item
  });

  it("nextReviewed returns null when every reviewed item is excluded (FR-11 exhaustion)", async () => {
    const db = new InMemoryEngineDb();
    db.seedQuestions([
      question({ id: "q1", reviewed: true }),
      question({ id: "q2", reviewed: true }),
    ]);
    const repo = new DrizzleQuestionRepo(db);
    expect(await repo.nextReviewed("act-english", "s-punct", ["q1", "q2"])).toBeNull();
  });

  it("excludeIds never surfaces a reviewed=false item (FR-12 gate intact)", async () => {
    const db = new InMemoryEngineDb();
    db.seedQuestions([
      question({ id: "r1", reviewed: true, difficulty: 5 }),
      question({ id: "u1", reviewed: false, difficulty: 1 }), // unreviewed, easiest
    ]);
    const repo = new DrizzleQuestionRepo(db);
    // Exclude the only reviewed item; the unreviewed easy one must NOT surface.
    expect(await repo.nextReviewed("act-english", "s-punct", ["r1"])).toBeNull();
  });

  it("empty excludeIds is identical to today's behaviour (backward-compat)", async () => {
    const db = new InMemoryEngineDb();
    db.seedQuestions([question({ id: "q1", reviewed: true, difficulty: 1 })]);
    const repo = new DrizzleQuestionRepo(db);
    expect((await repo.nextReviewed("act-english", "s-punct", []))!.id).toBe("q1");
  });
});

// --- AttemptRepo ---------------------------------------------------------

describe("DrizzleAttemptRepo — append-only + misses", () => {
  it("record assigns id+created_at and never lets used_hint change correctness (FR-D5)", async () => {
    const db = new InMemoryEngineDb();
    const repo = new DrizzleAttemptRepo({
      db,
      newId: () => "a1",
      now: () => new Date("2026-06-30T00:00:00Z"),
    });
    const saved = await repo.record({
      subject: "act-english",
      session_id: "sess1",
      question_id: "q1",
      chosen_letter: "A",
      correct: true,
      elapsed_ms: 1200,
      used_hint: true, // hinted...
      idempotency_key: "test-idem-1",
    });
    expect(saved.id).toBe("a1");
    expect(saved.created_at).toBe("2026-06-30T00:00:00.000Z");
    expect(saved.correct).toBe(true); // ...still correct
    expect(saved.used_hint).toBe(true);
  });

  it("record round-trips resolution; legacy omit reads nullish (FR-10)", async () => {
    const db = new InMemoryEngineDb();
    await db.insertSession({
      id: "sess1",
      subject: "act-english",
      learner_id: "alice",
      mode: "adaptive",
      skill_focus: null,
      started_at: "2026-07-19T00:00:00Z",
      ended_at: null,
      score_correct: 0,
      score_total: 0,
      target_count: null,
    });
    const repo = new DrizzleAttemptRepo({
      db,
      newId: () => "a-res",
      now: () => new Date("2026-07-19T00:00:00Z"),
    });
    const withRes = await repo.record({
      subject: "act-english",
      session_id: "sess1",
      question_id: "q1",
      chosen_letter: "B",
      correct: false,
      elapsed_ms: 100,
      used_hint: false,
      resolution: "walked_through",
      idempotency_key: "test-idem-2",
    });
    expect(withRes.resolution).toBe("walked_through");
    const misses = await repo.misses("act-english", "alice");
    expect(misses[0]?.resolution).toBe("walked_through");

    const legacy = await new DrizzleAttemptRepo({
      db: new InMemoryEngineDb(),
      newId: () => "a-legacy",
      now: () => new Date("2026-07-19T00:00:01Z"),
    }).record({
      subject: "act-english",
      session_id: "sess2",
      question_id: "q2",
      chosen_letter: "A",
      correct: true,
      elapsed_ms: 50,
      used_hint: false,
      idempotency_key: "test-idem-legacy",
    });
    expect(legacy.resolution == null).toBe(true);
  });

  it("misses returns outstanding incorrect attempts newest-first (FR-D4)", async () => {
    const db = new InMemoryEngineDb();
    // Two sessions for the learner; one attempt each.
    await db.insertSession({
      id: "sess1",
      subject: "act-english",
      learner_id: "alice",
      mode: "adaptive",
      skill_focus: null,
      started_at: "2026-06-30T00:00:00Z",
      ended_at: null,
      score_correct: 0,
      score_total: 0,
      target_count: null,
    });
    const repo = new DrizzleAttemptRepo({ db });
    await db.insertAttempt({
      id: "m1",
      subject: "act-english",
      session_id: "sess1",
      question_id: "q1",
      chosen_letter: "B",
      correct: false,
      elapsed_ms: 1,
      used_hint: false,
      created_at: "2026-06-30T00:00:01Z",
    });
    await db.insertAttempt({
      id: "m2",
      subject: "act-english",
      session_id: "sess1",
      question_id: "q2",
      chosen_letter: "C",
      correct: false,
      elapsed_ms: 1,
      used_hint: false,
      created_at: "2026-06-30T00:00:02Z",
    });
    await db.insertAttempt({
      id: "ok",
      subject: "act-english",
      session_id: "sess1",
      question_id: "q3",
      chosen_letter: "A",
      correct: true,
      elapsed_ms: 1,
      used_hint: false,
      created_at: "2026-06-30T00:00:03Z",
    });
    const misses = await repo.misses("act-english", "alice");
    expect(misses.map((m) => m.id)).toEqual(["m2", "m1"]); // newest-first, correct excluded
  });

  it("misses tie-breaks a same-created_at collision by insertion order, not by random id (FR-D4)", async () => {
    // Two misses stamped the SAME created_at (record() landing in one tick, or a
    // bulk import). `orderBy(desc(created_at))` alone leaves the order undefined,
    // and the old fake tie-broke on the random UUID `id` — surfacing an arbitrary
    // row. The summary recap must show the LAST miss recorded, so the deterministic
    // contract is: newest-inserted first. `id` is set so a naive id-desc tiebreak
    // would pick "aaa" (older) — proving the fix ignores id.
    const db = new InMemoryEngineDb();
    await db.insertSession({
      id: "sess1",
      subject: "act-english",
      learner_id: "alice",
      mode: "adaptive",
      skill_focus: null,
      started_at: "2026-06-30T00:00:00Z",
      ended_at: null,
      score_correct: 0,
      score_total: 0,
      target_count: null,
    });
    const repo = new DrizzleAttemptRepo({ db });
    const tie = "2026-06-30T00:00:05Z";
    await db.insertAttempt({
      id: "zzz-old", // recorded first; larger id string
      subject: "act-english",
      session_id: "sess1",
      question_id: "q-old",
      chosen_letter: "B",
      correct: false,
      elapsed_ms: 1,
      used_hint: false,
      created_at: tie,
    });
    await db.insertAttempt({
      id: "aaa-new", // recorded second; smaller id string
      subject: "act-english",
      session_id: "sess1",
      question_id: "q-new",
      chosen_letter: "C",
      correct: false,
      elapsed_ms: 1,
      used_hint: false,
      created_at: tie,
    });
    const misses = await repo.misses("act-english", "alice");
    // Newest-inserted (q-new) first, regardless of id ordering.
    expect(misses.map((m) => m.question_id)).toEqual(["q-new", "q-old"]);
  });

  it("record keeps created_at strictly increasing within a tick so ties never reach misses (FR-D4)", async () => {
    // The pg + in-memory adapters both order misses by created_at DESC with no
    // secondary key. If two record() calls share a wall-clock ms the timestamps
    // tie and the recap picks the wrong miss. record() must bump each stamp past
    // the previous one so the sole ordering key stays a total order.
    const db = new InMemoryEngineDb();
    await db.insertSession({
      id: "sess1",
      subject: "act-english",
      learner_id: "alice",
      mode: "adaptive",
      skill_focus: null,
      started_at: "2026-06-30T00:00:00Z",
      ended_at: null,
      score_correct: 0,
      score_total: 0,
      target_count: null,
    });
    let n = 0;
    const repo = new DrizzleAttemptRepo({
      db,
      newId: () => `a${n++}`,
      now: () => new Date("2026-06-30T00:00:00Z"), // frozen clock: every call ties
    });
    const first = await repo.record({
      subject: "act-english",
      session_id: "sess1",
      question_id: "q-old",
      chosen_letter: "B",
      correct: false,
      elapsed_ms: 1,
      used_hint: false,
      idempotency_key: "test-idem-3",
    });
    const second = await repo.record({
      subject: "act-english",
      session_id: "sess1",
      question_id: "q-new",
      chosen_letter: "C",
      correct: false,
      elapsed_ms: 1,
      used_hint: false,
      idempotency_key: "test-idem-4",
    });
    // First stamp equals the frozen clock; second is bumped +1ms (strictly newer).
    expect(first.created_at).toBe("2026-06-30T00:00:00.000Z");
    expect(second.created_at).toBe("2026-06-30T00:00:00.001Z");
    expect(second.created_at > first.created_at).toBe(true);
    const misses = await repo.misses("act-english", "alice");
    expect(misses.map((m) => m.question_id)).toEqual(["q-new", "q-old"]);
  });

  it("misses drops a question after a later correct attempt (clears review pool)", async () => {
    const db = new InMemoryEngineDb();
    await db.insertSession({
      id: "sess1",
      subject: "act-english",
      learner_id: "alice",
      mode: "adaptive",
      skill_focus: null,
      started_at: "2026-06-30T00:00:00Z",
      ended_at: null,
      score_correct: 0,
      score_total: 0,
      target_count: null,
    });
    await db.insertSession({
      id: "sess-review",
      subject: "act-english",
      learner_id: "alice",
      mode: "review",
      skill_focus: null,
      started_at: "2026-06-30T01:00:00Z",
      ended_at: null,
      score_correct: 0,
      score_total: 0,
      target_count: null,
    });
    const repo = new DrizzleAttemptRepo({ db });
    // Prior misses on q1 + q2
    await db.insertAttempt({
      id: "m1",
      subject: "act-english",
      session_id: "sess1",
      question_id: "q1",
      chosen_letter: "B",
      correct: false,
      elapsed_ms: 1,
      used_hint: false,
      created_at: "2026-06-30T00:00:01Z",
    });
    await db.insertAttempt({
      id: "m2",
      subject: "act-english",
      session_id: "sess1",
      question_id: "q2",
      chosen_letter: "C",
      correct: false,
      elapsed_ms: 1,
      used_hint: false,
      created_at: "2026-06-30T00:00:02Z",
    });
    // Review: clear q1, miss q2 again
    await db.insertAttempt({
      id: "ok1",
      subject: "act-english",
      session_id: "sess-review",
      question_id: "q1",
      chosen_letter: "A",
      correct: true,
      elapsed_ms: 1,
      used_hint: false,
      created_at: "2026-06-30T01:00:01Z",
    });
    await db.insertAttempt({
      id: "m2b",
      subject: "act-english",
      session_id: "sess-review",
      question_id: "q2",
      chosen_letter: "D",
      correct: false,
      elapsed_ms: 1,
      used_hint: false,
      created_at: "2026-06-30T01:00:02Z",
    });
    const misses = await repo.misses("act-english", "alice");
    expect(misses.map((m) => m.id)).toEqual(["m2b"]); // q1 cleared; q2 still outstanding
  });

  // --- S3: session-scoped served-ids (FR-13; no session-scoped read existed) ---

  it("servedQuestionIds returns exactly the session's answered question ids (served, not misses)", async () => {
    const db = new InMemoryEngineDb();
    const repo = new DrizzleAttemptRepo({ db });
    // sess1: two attempts (one CORRECT, one incorrect) — both are "served".
    await db.insertAttempt({
      id: "a1",
      subject: "act-english",
      session_id: "sess1",
      question_id: "q1",
      chosen_letter: "B",
      correct: true, // served regardless of correctness (unlike misses)
      elapsed_ms: 1,
      used_hint: false,
      created_at: "2026-07-08T00:00:01Z",
    });
    await db.insertAttempt({
      id: "a2",
      subject: "act-english",
      session_id: "sess1",
      question_id: "q2",
      chosen_letter: "C",
      correct: false,
      elapsed_ms: 1,
      used_hint: false,
      created_at: "2026-07-08T00:00:02Z",
    });
    // A DIFFERENT session's attempt must not leak into sess1's served set.
    await db.insertAttempt({
      id: "b1",
      subject: "act-english",
      session_id: "sess2",
      question_id: "q9",
      chosen_letter: "A",
      correct: true,
      elapsed_ms: 1,
      used_hint: false,
      created_at: "2026-07-08T00:00:03Z",
    });
    const served = await repo.servedQuestionIds("sess1");
    expect([...served].sort()).toEqual(["q1", "q2"]);
    expect(served).not.toContain("q9");
  });

  it("servedQuestionIds returns [] for a session with no attempts", async () => {
    const repo = new DrizzleAttemptRepo({ db: new InMemoryEngineDb() });
    expect(await repo.servedQuestionIds("sess-empty")).toEqual([]);
  });

  // --- S3.1: session-scoped served-SKILL read (FR-5) — round-robin rotation ---

  it("servedSkillIds returns this session's skills newest-first, distinct (FR-5)", async () => {
    const db = new InMemoryEngineDb();
    // Three questions across two skills; served punc, then gram, then punc again.
    db.seedQuestions([
      question({ id: "qp1", skill_id: "s-punc" }),
      question({ id: "qg1", skill_id: "s-gram" }),
      question({ id: "qp2", skill_id: "s-punc" }),
    ]);
    const repo = new DrizzleAttemptRepo({ db });
    const at = (n: number) => `2026-07-08T00:00:0${n}Z`;
    await db.insertAttempt({
      id: "a1", subject: "act-english", session_id: "sess1", question_id: "qp1",
      chosen_letter: "A", correct: true, elapsed_ms: 1, used_hint: false, created_at: at(1),
    });
    await db.insertAttempt({
      id: "a2", subject: "act-english", session_id: "sess1", question_id: "qg1",
      chosen_letter: "A", correct: false, elapsed_ms: 1, used_hint: false, created_at: at(2),
    });
    await db.insertAttempt({
      id: "a3", subject: "act-english", session_id: "sess1", question_id: "qp2",
      chosen_letter: "A", correct: true, elapsed_ms: 1, used_hint: false, created_at: at(3),
    });
    // newest-first by attempt time: qp2(s-punc,3) → qg1(s-gram,2) → qp1(s-punc,1),
    // de-duped keeping the newest occurrence's position → [s-punc, s-gram].
    const skills = await repo.servedSkillIds("sess1");
    expect([...skills]).toEqual(["s-punc", "s-gram"]);
  });

  it("servedSkillIds does not leak another session's skills (FR-5)", async () => {
    const db = new InMemoryEngineDb();
    db.seedQuestions([
      question({ id: "qp1", skill_id: "s-punc" }),
      question({ id: "qr1", skill_id: "s-rhet" }),
    ]);
    const repo = new DrizzleAttemptRepo({ db });
    await db.insertAttempt({
      id: "a1", subject: "act-english", session_id: "sess1", question_id: "qp1",
      chosen_letter: "A", correct: true, elapsed_ms: 1, used_hint: false,
      created_at: "2026-07-08T00:00:01Z",
    });
    await db.insertAttempt({
      id: "b1", subject: "act-english", session_id: "sess2", question_id: "qr1",
      chosen_letter: "A", correct: true, elapsed_ms: 1, used_hint: false,
      created_at: "2026-07-08T00:00:02Z",
    });
    const skills = await repo.servedSkillIds("sess1");
    expect([...skills]).toEqual(["s-punc"]);
    expect(skills).not.toContain("s-rhet");
  });

  it("servedSkillIds returns [] for a session with no attempts (FR-5)", async () => {
    const repo = new DrizzleAttemptRepo({ db: new InMemoryEngineDb() });
    expect(await repo.servedSkillIds("sess-empty")).toEqual([]);
  });

  it("servedSkillIds resolves BANK items too (attempt.question_id may be a test_item id) (FR-5)", async () => {
    // The bank quiz (ADR-0021) serves test_item ids, NOT question ids, so the
    // served-skill read must resolve skill from test_item as well as question —
    // otherwise rotation silently no-ops on the live /learn surface.
    const db = new InMemoryEngineDb();
    db.seedTestItems([
      {
        id: "ti-punc",
        subject: "act-english",
        skill_id: "s-punc",
        difficulty: 2,
        context_html: "<p>c</p>",
        stem_md: "Which choice is best?",
        choices: [
          { letter: "A", label: "NO CHANGE", is_no_change: true },
          { letter: "B", label: "b", is_no_change: false },
          { letter: "C", label: "c", is_no_change: false },
          { letter: "D", label: "d", is_no_change: false },
        ],
        answer_letter: "A",
        per_choice_rationale: { A: "correct" },
        why_correct_md: "because",
        why_tempted_md: "tempting",
        rule_md: "the rule",
        item_type: "underlined-span-mc",
        misconception: null,
        reviewed: true,
        generated_by: "test@run1",
      },
    ]);
    const repo = new DrizzleAttemptRepo({ db });
    await db.insertAttempt({
      id: "a1", subject: "act-english", session_id: "sessB", question_id: "ti-punc",
      chosen_letter: "A", correct: true, elapsed_ms: 1, used_hint: false,
      created_at: "2026-07-08T00:00:01Z",
    });
    expect([...(await repo.servedSkillIds("sessB"))]).toEqual(["s-punc"]);
  });

  it("FR-7: accuracyBySkill reads attempt only — never skill_state", async () => {
    const db = new InMemoryEngineDb();
    db.seedQuestions([question({ id: "q1", skill_id: "s-punct" })]);
    await db.insertSession({
      id: "sess1",
      subject: "act-english",
      learner_id: "alice",
      mode: "adaptive",
      skill_focus: null,
      started_at: "2026-06-30T00:00:00Z",
      ended_at: null,
      score_correct: 0,
      score_total: 0,
      target_count: null,
    });
    await db.insertAttempt({
      id: "a1",
      subject: "act-english",
      session_id: "sess1",
      question_id: "q1",
      chosen_letter: "A",
      correct: true,
      elapsed_ms: 1,
      used_hint: false,
      created_at: "2026-06-30T00:00:01Z",
    });
    // Poison mastery — accuracy must ignore it (FR-5/FR-7).
    await db.upsertSkillState({
      subject: "act-english",
      skill_id: "s-punct",
      learner_id: "alice",
      mastery: 0.99,
      last_seen: "2026-06-30T00:00:00Z",
      fsrs_stability: 10,
      fsrs_difficulty: 1,
      due_at: "2999-01-01T00:00:00Z",
      fsrs_card: null,
    });
    const repo = new DrizzleAttemptRepo({ db });
    const origGet = db.getSkillState.bind(db);
    const origList = db.listSkillState.bind(db);
    const origUpsert = db.upsertSkillState.bind(db);
    let skillStateReads = 0;
    let skillStateWrites = 0;
    db.getSkillState = async (...args) => {
      skillStateReads += 1;
      return origGet(...args);
    };
    db.listSkillState = async (...args) => {
      skillStateReads += 1;
      return origList(...args);
    };
    db.upsertSkillState = async (...args) => {
      skillStateWrites += 1;
      return origUpsert(...args);
    };
    const acc = await repo.accuracyBySkill("act-english", "alice", "s-punct");
    expect(acc).toEqual({ valuePct: 100, bars: [100] });
    expect(skillStateReads).toBe(0);
    expect(skillStateWrites).toBe(0);
  });

  it("FR-8: hinted-but-correct counts as correct in accuracyBySkill", async () => {
    const db = new InMemoryEngineDb();
    db.seedQuestions([question({ id: "q1", skill_id: "s-punct" })]);
    await db.insertSession({
      id: "sess1",
      subject: "act-english",
      learner_id: "alice",
      mode: "adaptive",
      skill_focus: null,
      started_at: "2026-06-30T00:00:00Z",
      ended_at: null,
      score_correct: 0,
      score_total: 0,
      target_count: null,
    });
    await db.insertAttempt({
      id: "a1",
      subject: "act-english",
      session_id: "sess1",
      question_id: "q1",
      chosen_letter: "A",
      correct: true,
      elapsed_ms: 1,
      used_hint: true, // hinted… still correct (FR-D5 / FR-8)
      created_at: "2026-06-30T00:00:01Z",
    });
    const repo = new DrizzleAttemptRepo({ db });
    const acc = await repo.accuracyBySkill("act-english", "alice", "s-punct");
    expect(acc).toEqual({ valuePct: 100, bars: [100] });
  });

  it("accuracyBySkill join counts bank(test_item) attempts via COALESCE", async () => {
    const db = new InMemoryEngineDb();
    db.seedTestItems([
      {
        id: "ti-punc",
        subject: "act-english",
        skill_id: "s-punc",
        difficulty: 2,
        context_html: "<p>c</p>",
        stem_md: "Which choice is best?",
        choices: [
          { letter: "A", label: "NO CHANGE", is_no_change: true },
          { letter: "B", label: "b", is_no_change: false },
          { letter: "C", label: "c", is_no_change: false },
          { letter: "D", label: "d", is_no_change: false },
        ],
        answer_letter: "A",
        per_choice_rationale: { A: "correct" },
        why_correct_md: "because",
        why_tempted_md: "tempting",
        rule_md: "the rule",
        item_type: "underlined-span-mc",
        misconception: null,
        reviewed: true,
        generated_by: "test@run1",
      },
    ]);
    await db.insertSession({
      id: "sessB",
      subject: "act-english",
      learner_id: "alice",
      mode: "adaptive",
      skill_focus: null,
      started_at: "2026-07-08T00:00:00Z",
      ended_at: null,
      score_correct: 0,
      score_total: 0,
      target_count: null,
    });
    await db.insertAttempt({
      id: "a1",
      subject: "act-english",
      session_id: "sessB",
      question_id: "ti-punc",
      chosen_letter: "A",
      correct: true,
      elapsed_ms: 1,
      used_hint: false,
      created_at: "2026-07-08T00:00:01Z",
    });
    const repo = new DrizzleAttemptRepo({ db });
    const acc = await repo.accuracyBySkill("act-english", "alice", "s-punc");
    expect(acc).toEqual({ valuePct: 100, bars: [100] });
  });

  it("accuracyBySkill returns null when learner has no on-skill attempts", async () => {
    const repo = new DrizzleAttemptRepo({ db: new InMemoryEngineDb() });
    expect(await repo.accuracyBySkill("act-english", "alice", "s-punct")).toBeNull();
  });
});

// --- SessionRepo ---------------------------------------------------------

describe("DrizzleSessionRepo — lifecycle + scoring", () => {
  it("open creates a started, unscored session; close stores the tally (FR-D1/D3)", async () => {
    const db = new InMemoryEngineDb();
    let t = 0;
    const repo = new DrizzleSessionRepo({
      db,
      newId: () => "sess1",
      now: () => new Date(2026, 5, 30, 0, 0, t++),
    });
    const opened = await repo.open("act-english", "alice", "drill", "s-punct");
    expect(opened.ended_at).toBeNull();
    expect(opened.skill_focus).toBe("s-punct");
    expect(opened.score_total).toBe(0);

    const closed = await repo.close("sess1", { score_correct: 7, score_total: 10 });
    expect(closed.ended_at).not.toBeNull();
    expect(closed.score_correct).toBe(7);
    expect(closed.score_total).toBe(10);

    // Summary reads the STORED tally, not a recompute.
    const reread = await repo.get("sess1");
    expect(reread!.score_correct).toBe(7);
  });

  it("close is idempotent: re-close preserves the first ended_at, not just the tally", async () => {
    const db = new InMemoryEngineDb();
    let t = 0;
    const repo = new DrizzleSessionRepo({
      db,
      newId: () => "sess1",
      now: () => new Date(2026, 5, 30, 0, 0, t++), // each call advances the clock
    });
    await repo.open("act-english", "alice", "adaptive");
    const first = await repo.close("sess1", { score_correct: 3, score_total: 5 });
    const second = await repo.close("sess1", { score_correct: 3, score_total: 5 });
    expect(second.score_correct).toBe(3);
    // The clock advanced between closes, but ended_at must NOT move (idempotent).
    expect(second.ended_at).toBe(first.ended_at);
  });

  it("close throws EngineNotFoundError for an unknown session", async () => {
    const repo = new DrizzleSessionRepo({ db: new InMemoryEngineDb() });
    await expect(
      repo.close("nope", { score_correct: 0, score_total: 0 }),
    ).rejects.toBeInstanceOf(EngineNotFoundError);
  });

  // --- S3: bounded-session target_count (FR-5/6/7) ---

  function sessionRepoWithContent(
    content: Record<string, string> = {},
  ): { db: InMemoryEngineDb; repo: DrizzleSessionRepo } {
    const db = new InMemoryEngineDb();
    if (Object.keys(content).length) db.seedContent("act-english", "en", content);
    const repo = new DrizzleSessionRepo({
      db,
      contentRepo: new DrizzleContentRepo(db),
      newId: () => "sess-tc",
      now: () => new Date(2026, 6, 8, 0, 0, 0),
    });
    return { db, repo };
  }

  it("open without a target resolves the per-mode default 30 from content_string (FR-5)", async () => {
    const { repo } = sessionRepoWithContent({
      "session.target_count.drill": "30",
    });
    const opened = await repo.open("act-english", "alice", "drill", "s-punct");
    expect(opened.target_count).toBe(30);
  });

  it("open without a target falls back to 30 when no content_string row exists (FR-5)", async () => {
    // Missing policy row → ContentRepo echoes the key; the repo must still land
    // on the flat-30 default, never persist a NaN/key-string as the length.
    const { repo } = sessionRepoWithContent();
    const opened = await repo.open("act-english", "alice", "adaptive");
    expect(opened.target_count).toBe(30);
  });

  it("open with an explicit target persists that value, not the default (FR-6)", async () => {
    const { repo } = sessionRepoWithContent({
      "session.target_count.drill": "30",
    });
    const opened = await repo.open("act-english", "alice", "drill", "s-punct", 12);
    expect(opened.target_count).toBe(12);
  });

  it("open with an explicit null = endless session, distinct from omitted (FR-2/FR-6)", async () => {
    const { repo } = sessionRepoWithContent({
      "session.target_count.drill": "30",
    });
    const opened = await repo.open("act-english", "alice", "drill", "s-punct", null);
    expect(opened.target_count).toBeNull();
  });

  it("close leaves target_count untouched — stored, not recomputed (FR-7)", async () => {
    const { repo } = sessionRepoWithContent({
      "session.target_count.drill": "30",
    });
    await repo.open("act-english", "alice", "drill", "s-punct");
    const closed = await repo.close("sess-tc", { score_correct: 5, score_total: 8 });
    expect(closed.target_count).toBe(30);
  });
});

describe("DrizzleSessionRepo — listByLearner (ADR-0026 / C1 rail)", () => {
  function closedSession(over: {
    id: string;
    ended_at: string | null;
    subject?: string;
    learner_id?: string;
  }) {
    return {
      id: over.id,
      subject: over.subject ?? "act-english",
      learner_id: over.learner_id ?? "maya",
      mode: "adaptive" as const,
      skill_focus: null,
      started_at: "2026-07-01T00:00:00.000Z",
      ended_at: over.ended_at,
      score_correct: 1,
      score_total: 1,
      target_count: 30,
    };
  }

  it("sessionRepo_listByLearner_rejects_translated_to_EngineRepoError", async () => {
    const repo = new DrizzleSessionRepo({ db: rejectingDb() });
    await expect(
      repo.listByLearner("act-english", "maya"),
    ).rejects.toBeInstanceOf(EngineRepoError);
  });

  it("sessionRepo_listByLearner_empty_returns_empty_array", async () => {
    const repo = new DrizzleSessionRepo({ db: new InMemoryEngineDb() });
    expect(await repo.listByLearner("act-english", "maya")).toEqual([]);
  });

  it("sessionRepo_listByLearner_excludes_inflight", async () => {
    const db = new InMemoryEngineDb();
    await db.insertSession(
      closedSession({ id: "closed", ended_at: "2026-07-08T12:00:00.000Z" }),
    );
    await db.insertSession(closedSession({ id: "open", ended_at: null }));
    const repo = new DrizzleSessionRepo({ db });
    const out = await repo.listByLearner("act-english", "maya");
    expect(out.map((s) => s.id)).toEqual(["closed"]);
  });

  it("sessionRepo_listByLearner_newest_first_with_id_tiebreak", async () => {
    const db = new InMemoryEngineDb();
    const sameEnd = "2026-07-08T12:00:00.000Z";
    await db.insertSession(closedSession({ id: "c", ended_at: sameEnd }));
    await db.insertSession(closedSession({ id: "a", ended_at: sameEnd }));
    await db.insertSession(closedSession({ id: "b", ended_at: sameEnd }));
    const repo = new DrizzleSessionRepo({ db });
    const out = await repo.listByLearner("act-english", "maya");
    expect(out.map((s) => s.id)).toEqual(["a", "b", "c"]);
  });

  it("sessionRepo_listByLearner_sinceISO_inclusive_lower_bound", async () => {
    const db = new InMemoryEngineDb();
    const bound = "2026-07-05T00:00:00.000Z";
    await db.insertSession(
      closedSession({ id: "before", ended_at: "2026-07-04T23:59:59.000Z" }),
    );
    await db.insertSession(closedSession({ id: "at", ended_at: bound }));
    await db.insertSession(
      closedSession({ id: "after", ended_at: "2026-07-06T00:00:00.000Z" }),
    );
    const repo = new DrizzleSessionRepo({ db });
    const out = await repo.listByLearner("act-english", "maya", {
      sinceISO: bound,
    });
    expect(out.map((s) => s.id).sort()).toEqual(["after", "at"]);
  });

  it("sessionRepo_listByLearner_subject_scoped", async () => {
    const db = new InMemoryEngineDb();
    await db.insertSession(
      closedSession({
        id: "eng",
        ended_at: "2026-07-08T12:00:00.000Z",
        subject: "act-english",
      }),
    );
    await db.insertSession(
      closedSession({
        id: "alg",
        ended_at: "2026-07-08T13:00:00.000Z",
        subject: "algebra-i",
      }),
    );
    const repo = new DrizzleSessionRepo({ db });
    const out = await repo.listByLearner("act-english", "maya");
    expect(out.map((s) => s.id)).toEqual(["eng"]);
  });
});

// --- ContentRepo ---------------------------------------------------------

describe("DrizzleContentRepo — objective plane", () => {
  it("text returns the value, or the key itself on a miss (never throws on miss)", async () => {
    const db = new InMemoryEngineDb();
    db.seedContent("act-english", "en", {
      "screen.dashboard.greeting": "Welcome back",
    });
    const repo = new DrizzleContentRepo(db);
    expect(await repo.text("act-english", "screen.dashboard.greeting")).toBe(
      "Welcome back",
    );
    expect(await repo.text("act-english", "missing.key")).toBe("missing.key");
  });

  it("bundle returns the full (subject, locale) map", async () => {
    const db = new InMemoryEngineDb();
    db.seedContent("act-english", "en", { a: "1", b: "2" });
    db.seedContent("act-english", "es", { a: "uno" });
    const repo = new DrizzleContentRepo(db);
    expect(await repo.bundle("act-english")).toEqual({ a: "1", b: "2" });
  });

  it("translates a db rejection to EngineRepoError", async () => {
    const repo = new DrizzleContentRepo(rejectingDb());
    await expect(repo.text("act-english", "k")).rejects.toBeInstanceOf(
      EngineRepoError,
    );
  });
});

// --- LearnerReadRepo (ADR-0011) -----------------------------------------

function skillState(over: Partial<SkillState> = {}): SkillState {
  return {
    subject: "act-english",
    skill_id: "s-punct",
    learner_id: "maya",
    mastery: 0.42,
    last_seen: "2026-06-20T10:00:00.000Z",
    fsrs_stability: 3,
    fsrs_difficulty: 5,
    due_at: "2026-06-25T10:00:00.000Z",
    fsrs_card: null,
    ...over,
  };
}

describe("DrizzleLearnerReadRepo — read-only skill_state (ADR-0011)", () => {
  it("translates a db rejection to EngineRepoError (no vendor type escapes)", async () => {
    const repo = new DrizzleLearnerReadRepo(rejectingDb());
    await expect(repo.listSkillState("act-english", "maya")).rejects.toBeInstanceOf(
      EngineRepoError,
    );
  });

  it("brand-new learner (no rows) → empty array, not a throw (FR-C3 placeholder)", async () => {
    const repo = new DrizzleLearnerReadRepo(new InMemoryEngineDb());
    expect(await repo.listSkillState("act-english", "maya")).toEqual([]);
  });

  it("reads what the Scheduler wrote, scoped to (subject, learner)", async () => {
    const db = new InMemoryEngineDb();
    // The Scheduler is the sole writer (FR-A2); seed via its write path.
    await db.upsertSkillState(skillState({ skill_id: "s-punct", mastery: 0.42 }));
    await db.upsertSkillState(skillState({ skill_id: "s-conc", mastery: 0.7 }));
    await db.upsertSkillState(skillState({ learner_id: "OTHER", skill_id: "s-punct" }));
    await db.upsertSkillState(skillState({ subject: "algebra-i", skill_id: "s-lin" }));

    const repo = new DrizzleLearnerReadRepo(db);
    const rows = await repo.listSkillState("act-english", "maya");

    expect(rows.map((r) => r.skill_id).sort()).toEqual(["s-conc", "s-punct"]);
    expect(rows.every((r) => r.subject === "act-english" && r.learner_id === "maya")).toBe(true);
  });
});
