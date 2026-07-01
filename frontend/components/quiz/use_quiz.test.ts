/**
 * Phase 1.3 — Quiz orchestration (FR-D1..D8, L1 deterministic).
 *
 * Per F-R1 the Quiz component owns NO domain logic: the whole
 * next→get→grade→record→review sequence lives here, in the React-free
 * `runQuizSubmit` / `openQuizItem` orchestration exercised in node against a
 * seeded InMemoryEngineDb (no React, no mocks-of-internals — a real fake).
 *
 * Failure path first (Anti-Pattern 6): a no-selection submit (FR-D2a/D4) must
 * record NO attempt and return no verdict — BEFORE the correct/wrong paths.
 */

import { describe, expect, it, beforeEach } from "vitest";
import { InMemoryEngineDb } from "@/lib/adapters/engine/db/in_memory_engine_db";
import { buildBrowserEngineAdapters } from "@/lib/composition_engine_browser";
import type { EnginePortBag } from "@/lib/composition_engine";
import { openQuizItem, openQuizSession, runQuizSubmit } from "./use_quiz";
import type { Question, Skill, SkillState } from "@/lib/wire/engine_entities";

const SUBJECT = "act-english";
const LEARNER = "maya";

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

function question(over: Partial<Question> = {}): Question {
  return {
    id: "q1",
    subject: SUBJECT,
    skill_id: "s-punc",
    difficulty: 3,
    context_html: "The committee <u>have</u> decided.",
    stem: "Which choice is best?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "has", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: { A: "A tempted you", B: "B is correct" },
    why_correct_md: "…",
    why_tempted_md: "…",
    rule_md: "…",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

function skillState(over: Partial<SkillState> = {}): SkillState {
  return {
    subject: SUBJECT,
    skill_id: "s-punc",
    learner_id: LEARNER,
    mastery: 0.42,
    last_seen: "2026-06-25T00:00:00.000Z",
    fsrs_stability: 3,
    fsrs_difficulty: 5,
    due_at: "2026-07-01T00:00:00.000Z",
    fsrs_card: null,
    ...over,
  };
}

let db: InMemoryEngineDb;
let ports: EnginePortBag;

beforeEach(() => {
  db = new InMemoryEngineDb();
  db.seedSkills([skill()]);
  db.seedQuestions([question()]);
  ports = buildBrowserEngineAdapters({ engineDb: db });
});

describe("runQuizSubmit — no selection (failure path first, FR-D2a/D4)", () => {
  it("null letter records NO attempt and returns no verdict", async () => {
    const session = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    const result = await runQuizSubmit(ports, {
      session,
      question: question(),
      learnerId: LEARNER,
      letter: null,
      elapsedMs: 1000,
      usedHint: false,
    });
    expect(result.verdict).toBeNull();
    expect(result.attempt).toBeNull();
    const misses = await ports.attemptRepo.misses(SUBJECT, LEARNER);
    expect(misses).toHaveLength(0);
  });
});

describe("runQuizSubmit — grade → record → review (FR-D2/D3/A2)", () => {
  it("correct answer: verdict.correct true, attempt recorded, skill_state updated", async () => {
    const session = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    const result = await runQuizSubmit(ports, {
      session,
      question: question({ answer_letter: "B" }),
      learnerId: LEARNER,
      letter: "B",
      elapsedMs: 2000,
      usedHint: false,
    });
    expect(result.verdict?.correct).toBe(true);
    expect(result.attempt?.correct).toBe(true);
    expect(result.attempt?.chosen_letter).toBe("B");
    expect(result.skillState).not.toBeNull();
    expect(result.skillState?.skill_id).toBe("s-punc");
  });

  it("wrong answer: verdict.correct false and the attempt shows up in misses", async () => {
    const session = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    const result = await runQuizSubmit(ports, {
      session,
      question: question({ answer_letter: "B" }),
      learnerId: LEARNER,
      letter: "A",
      elapsedMs: 3000,
      usedHint: true,
    });
    expect(result.verdict?.correct).toBe(false);
    const misses = await ports.attemptRepo.misses(SUBJECT, LEARNER);
    expect(misses).toHaveLength(1);
    expect(misses[0]?.used_hint).toBe(true);
  });
});

describe("openQuizSession — session open + skillStateAtStart snapshot (FR-G1, ADR-0011 §4)", () => {
  it("brand-new learner: opens a session and captures an EMPTY snapshot (delta '—' path)", async () => {
    // Edge path first: a learner the scheduler has never seen has no skill_state
    // rows, so the "before" snapshot is empty — the Summary delta later renders "—".
    const result = await openQuizSession(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      mode: "adaptive",
    });
    expect(result.session.subject).toBe(SUBJECT);
    expect(result.session.ended_at).toBeNull();
    expect(result.skillStateAtStart.size).toBe(0);
  });

  it("captures the pre-session mastery once, keyed by skill_id", async () => {
    db.seedSkillStates([
      skillState({ skill_id: "s-punc", mastery: 0.42 }),
      skillState({ skill_id: "s-grammar", mastery: 0.7 }),
    ]);
    const result = await openQuizSession(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      mode: "adaptive",
    });
    expect(result.skillStateAtStart.size).toBe(2);
    expect(result.skillStateAtStart.get("s-punc")?.mastery).toBe(0.42);
    expect(result.skillStateAtStart.get("s-grammar")?.mastery).toBe(0.7);
  });

  it("snapshot is taken at open, BEFORE any review mutates skill_state (the 'before' half)", async () => {
    db.seedSkillStates([skillState({ skill_id: "s-punc", mastery: 0.42 })]);
    const { session, skillStateAtStart } = await openQuizSession(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      mode: "adaptive",
    });
    // A review runs and moves mastery; the snapshot must NOT track that change.
    await runQuizSubmit(ports, {
      session,
      question: question({ answer_letter: "B" }),
      learnerId: LEARNER,
      letter: "B",
      elapsedMs: 2000,
      usedHint: false,
    });
    const fresh = await ports.learnerRead.listSkillState(SUBJECT, LEARNER);
    const freshPunc = fresh.find((s) => s.skill_id === "s-punc");
    // The snapshot froze the pre-review value; the live read reflects the review.
    expect(skillStateAtStart.get("s-punc")?.mastery).toBe(0.42);
    expect(freshPunc?.mastery).not.toBe(0.42);
  });

  it("passes `focus` through to sessionRepo.open for a drill session (FR-A5)", async () => {
    const result = await openQuizSession(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      mode: "drill",
      focus: "s-punc",
    });
    expect(result.session.skill_focus).toBe("s-punc");
  });
});

describe("openQuizItem — scheduler pick → reviewed question (FR-A1/B*)", () => {
  it("returns a reviewed question for the scheduled skill", async () => {
    const item = await openQuizItem(ports, { subject: SUBJECT, learnerId: LEARNER });
    expect(item.question.reviewed).toBe(true);
    expect(item.question.id).toBe("q1");
    expect(item.skillId).toBe("s-punc");
  });
});
