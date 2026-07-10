/**
 * Phase 1.6 — Summary orchestration (FR-G1..G3, L1 deterministic).
 *
 * Per F-R1 the Summary component owns NO domain logic. Reading the STORED
 * session score (never a re-tally, FR-G1), diffing the mastery snapshot against
 * a fresh read for the delta (ADR-0011 §4), and picking the recommended-next
 * skill (FR-G1/G2) all live here, in the React-free `loadSummary` exercised in
 * node against a seeded InMemoryEngineDb.
 *
 * READ-ONLY (FR-A2): Summary is a *view* — it reads via `sessionRepo.get` +
 * `learnerRead.listSkillState` and never writes skill_state (no scheduler.next).
 *
 * Failure/edge path first: an absent start-snapshot for the focus skill (a
 * brand-new learner) makes the delta UNKNOWN → the view renders "—" (ADR §4),
 * not a fabricated "+0%".
 */

import { describe, expect, it, beforeEach } from "vitest";
import { InMemoryEngineDb } from "@/lib/adapters/engine/db/in_memory_engine_db";
import { buildBrowserEngineAdapters } from "@/lib/composition_engine_browser";
import type { EnginePortBag } from "@/lib/composition_engine";
import { loadSummary } from "./use_summary";
import type { Skill, SkillState, QuizSession } from "@/lib/wire/engine_entities";

const SUBJECT = "act-english";
const LEARNER = "maya";
const NOW = "2026-07-01T12:00:00.000Z";

function skill(over: Partial<Skill> = {}): Skill {
  return {
    id: "s-punc",
    subject: SUBJECT,
    key: "punctuation",
    name: "Punctuation",
    share_of_test_pct: 20,
    accent_var: "--color-bucket-punctuation",
    description: "…",
    order: 1,
    ...over,
  };
}

function skillState(over: Partial<SkillState> = {}): SkillState {
  return {
    subject: SUBJECT,
    skill_id: "s-punc",
    learner_id: LEARNER,
    mastery: 0.5,
    last_seen: "2026-06-25T00:00:00.000Z",
    fsrs_stability: 3,
    fsrs_difficulty: 5,
    due_at: "2026-06-20T00:00:00.000Z", // due (past) so it is the weakest+due pick
    fsrs_card: null,
    ...over,
  };
}

let db: InMemoryEngineDb;
let ports: EnginePortBag;

beforeEach(() => {
  db = new InMemoryEngineDb();
  db.seedSkills([skill(), skill({ id: "s-gram", key: "grammar", name: "Grammar", order: 2 })]);
  ports = buildBrowserEngineAdapters({ engineDb: db });
});

async function openClosedSession(over: Partial<QuizSession> = {}): Promise<QuizSession> {
  const s = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
  return ports.sessionRepo.close(s.id, { score_correct: 7, score_total: 10 });
}

describe("loadSummary — absent start-snapshot (edge path first, ADR §4)", () => {
  it("unknown start mastery → delta UNKNOWN so the view renders '—'", async () => {
    db.seedSkillStates([skillState({ skill_id: "s-punc", mastery: 0.6 })]);
    const session = await openClosedSession();
    const vm = await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map(), // brand-new learner: nothing captured at open
      nowISO: NOW,
    });
    expect(vm.masteryDeltaKnown).toBe(false);
  });
});

describe("loadSummary — stored score, never recomputed (FR-G1)", () => {
  it("score tile reads the STORED score even if attempts disagree", async () => {
    db.seedSkillStates([skillState()]);
    const session = await openClosedSession();
    const vm = await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map([["s-punc", skillState({ mastery: 0.5 })]]),
      nowISO: NOW,
    });
    expect(vm.summary.scoreTile).toBe("7/10");
    expect(vm.summary.scoreCorrect).toBe(7);
    expect(vm.summary.scoreTotal).toBe(10);
  });

  it("throws when the session id is unknown (a seam defect, surfaced)", async () => {
    await expect(
      loadSummary(ports, {
        subject: SUBJECT,
        learnerId: LEARNER,
        sessionId: "does-not-exist",
        skillStateAtStart: new Map(),
        nowISO: NOW,
      }),
    ).rejects.toThrow(/session/i);
  });
});

describe("loadSummary — signed mastery delta from the snapshot (FR-G1, ADR §4)", () => {
  it("current − start for the focus skill, ×100, signed", async () => {
    // Start mastery 0.50; fresh read 0.62 → +12%.
    db.seedSkillStates([skillState({ skill_id: "s-punc", mastery: 0.62 })]);
    const session = await openClosedSession();
    const vm = await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map([["s-punc", skillState({ skill_id: "s-punc", mastery: 0.5 })]]),
      nowISO: NOW,
    });
    expect(vm.masteryDeltaKnown).toBe(true);
    expect(vm.summary.masteryDeltaTile).toBe("+12%");
  });

  it("a mastery drop keeps its sign", async () => {
    db.seedSkillStates([skillState({ skill_id: "s-punc", mastery: 0.47 })]);
    const session = await openClosedSession();
    const vm = await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map([["s-punc", skillState({ skill_id: "s-punc", mastery: 0.5 })]]),
      nowISO: NOW,
    });
    expect(vm.summary.masteryDeltaTile).toBe("-3%");
  });
});

describe("loadSummary — recommended next re-opens Quiz on the weakest+due skill (FR-G1/G2)", () => {
  it("names the weakest+due skill and a drill mode", async () => {
    // s-punc is due+weaker; s-gram not due.
    db.seedSkillStates([
      skillState({ skill_id: "s-punc", mastery: 0.4, due_at: "2026-06-20T00:00:00.000Z" }),
      skillState({ skill_id: "s-gram", mastery: 0.9, due_at: "2026-08-01T00:00:00.000Z" }),
    ]);
    const session = await openClosedSession();
    const vm = await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map([["s-punc", skillState({ skill_id: "s-punc", mastery: 0.4 })]]),
      nowISO: NOW,
    });
    expect(vm.summary.recommended.skillId).toBe("s-punc");
    expect(vm.summary.recommended.skillName).toBe("Punctuation");
    expect(vm.summary.recommended.mode).toBe("drill");
  });
});

describe("loadSummary — read-only (FR-A2): renders without writing skill_state", () => {
  it("creates no new skill_state rows for a learner with none seeded", async () => {
    const session = await openClosedSession();
    await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map(),
      nowISO: NOW,
    });
    const rows = await ports.learnerRead.listSkillState(SUBJECT, LEARNER);
    expect(rows).toHaveLength(0);
  });
});

function question(over: Partial<import("@/lib/wire/engine_entities").Question> = {}) {
  return {
    id: "q1",
    subject: SUBJECT,
    skill_id: "s-punc",
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
    misconception: null as string | null,
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

async function recordAttempt(
  sessionId: string,
  questionId: string,
  correct: boolean,
): Promise<void> {
  await ports.attemptRepo.record({
    subject: SUBJECT,
    session_id: sessionId,
    question_id: questionId,
    chosen_letter: correct ? "A" : "B",
    correct,
    elapsed_ms: 1000,
    used_hint: false,
  });
}

describe("loadSummary — C2 misconception + self-correction (FR-1/FR-2/FR-12/FR-14)", () => {
  it("renders_no_misconception_card_when_question_misconception_null", async () => {
    db.seedSkillStates([skillState()]);
    db.seedQuestions([question({ id: "q-null", misconception: null })]);
    const session = await openClosedSession();
    await recordAttempt(session.id, "q-null", false);
    const vm = await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map([["s-punc", skillState()]]),
      nowISO: NOW,
    });
    expect(vm.summary.misconception).toBeNull();
  });

  it("renders_no_misconception_when_no_misses_on_recommended_skill", async () => {
    db.seedSkillStates([skillState()]);
    db.seedQuestions([
      question({ id: "q-gram", skill_id: "s-gram", misconception: "wrong skill miss" }),
      question({ id: "q-punc-ok", skill_id: "s-punc", misconception: "should not show" }),
    ]);
    const session = await openClosedSession();
    await recordAttempt(session.id, "q-gram", false); // miss on other skill
    await recordAttempt(session.id, "q-punc-ok", true); // correct on recommended
    const vm = await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map([["s-punc", skillState()]]),
      nowISO: NOW,
    });
    expect(vm.summary.misconception).toBeNull();
  });

  it("derives_misconception_from_last_incorrect_attempt_on_recommended_skill", async () => {
    db.seedSkillStates([skillState()]);
    db.seedQuestions([
      question({ id: "q-old", misconception: "older miss" }),
      question({ id: "q-new", misconception: "newest miss on skill" }),
    ]);
    const session = await openClosedSession();
    await recordAttempt(session.id, "q-old", false);
    await recordAttempt(session.id, "q-new", false);
    const vm = await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map([["s-punc", skillState()]]),
      nowISO: NOW,
    });
    expect(vm.summary.misconception).toBe("newest miss on skill");
  });

  it("self_correction_signal_true_when_first_half_miss_second_half_clean", async () => {
    db.seedSkillStates([skillState()]);
    db.seedQuestions([
      question({ id: "q1", misconception: "pattern" }),
      question({ id: "q2" }),
      question({ id: "q3" }),
      question({ id: "q4" }),
    ]);
    const session = await openClosedSession();
    // 4 attempts on recommended skill: miss, miss | correct, correct
    await recordAttempt(session.id, "q1", false);
    await recordAttempt(session.id, "q2", false);
    await recordAttempt(session.id, "q3", true);
    await recordAttempt(session.id, "q4", true);
    const vm = await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map([["s-punc", skillState()]]),
      nowISO: NOW,
    });
    expect(vm.summary.selfCorrected).toBe(true);
  });

  it("self_correction_signal_false_when_second_half_still_missing", async () => {
    db.seedSkillStates([skillState()]);
    db.seedQuestions([
      question({ id: "q1", misconception: "pattern" }),
      question({ id: "q2" }),
      question({ id: "q3" }),
      question({ id: "q4" }),
    ]);
    const session = await openClosedSession();
    await recordAttempt(session.id, "q1", false);
    await recordAttempt(session.id, "q2", true);
    await recordAttempt(session.id, "q3", false); // miss in second half
    await recordAttempt(session.id, "q4", true);
    const vm = await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map([["s-punc", skillState()]]),
      nowISO: NOW,
    });
    expect(vm.summary.selfCorrected).toBe(false);
  });

  it("normalizes_empty_string_misconception_to_null", async () => {
    db.seedSkillStates([skillState()]);
    db.seedQuestions([question({ id: "q-empty", misconception: "" })]);
    const session = await openClosedSession();
    await recordAttempt(session.id, "q-empty", false);
    const vm = await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map([["s-punc", skillState()]]),
      nowISO: NOW,
    });
    expect(vm.summary.misconception).toBeNull();
  });
});
