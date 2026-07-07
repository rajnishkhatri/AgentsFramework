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
import {
  closeQuizSession,
  openQuizItem,
  openQuizSession,
  runQuizSubmit,
} from "./use_quiz";
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

function bankItem(over: Partial<import("@/lib/wire/engine_entities").TestItem> = {}) {
  return {
    id: "ti-gen-bank0000item0001",
    subject: SUBJECT,
    skill_id: "s-punc",
    difficulty: 2,
    context_html: "The recipe calls for three <u>ingredients flour</u>, sugar, and butter.",
    stem_md: "Which choice correctly punctuates the introduction of the list?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "ingredients: flour", is_no_change: false },
      { letter: "C", label: "ingredients; flour", is_no_change: false },
      { letter: "D", label: "ingredients', flour", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: { A: "a…", B: "b…", C: "c…", D: "d…" },
    why_correct_md: "A colon introduces the list.",
    why_tempted_md: "Reads smoothly aloud.",
    rule_md: "Colon after a complete clause introduces a list.",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "gpt-4o-mini@run-1",
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

describe("bank-backed quiz (ADR-0021 — questionSource: 'bank')", () => {
  let bankDb: InMemoryEngineDb;
  let bankPorts: EnginePortBag;

  beforeEach(() => {
    bankDb = new InMemoryEngineDb();
    bankDb.seedSkills([skill()]);
    // NO question rows — the bank is the sole quiz source (FR-B2/B2a).
    bankDb.seedTestItems([bankItem()]);
    bankPorts = buildBrowserEngineAdapters({
      engineDb: bankDb,
      questionSource: "bank",
    });
  });

  it("openQuizItem serves a reviewed bank item, not a question row (FR-B2)", async () => {
    const item = await openQuizItem(bankPorts, {
      subject: SUBJECT,
      learnerId: LEARNER,
    });
    expect(item.question.id).toBe("ti-gen-bank0000item0001");
    // Lossless mapping: the Feedback payload is present (FR-C4).
    expect(item.question.per_choice_rationale["B"]).toBeTruthy();
    expect(item.question.rule_md).toContain("Colon");
    // No authored hints for bank items this increment → generic-nudge fallback.
    expect(item.hintLadder).toEqual([]);
  });

  it("runQuizSubmit grades + FSRS-reviews an attempt on a bank id (FR-B6)", async () => {
    const { session } = await openQuizSession(bankPorts, {
      subject: SUBJECT,
      learnerId: LEARNER,
      mode: "adaptive",
    });
    const { question: served } = await openQuizItem(bankPorts, {
      subject: SUBJECT,
      learnerId: LEARNER,
    });
    const result = await runQuizSubmit(bankPorts, {
      session,
      question: served,
      learnerId: LEARNER,
      letter: "B",
      elapsedMs: 1200,
      usedHint: false,
    });
    expect(result.verdict?.correct).toBe(true);
    expect(result.attempt?.question_id).toBe("ti-gen-bank0000item0001");
    // The FSRS review resolved the bank item's skill through the bank adapter.
    expect(result.skillState?.skill_id).toBe("s-punc");
  });

  it("fails closed when the scheduled skill has no bank item (FR-B4)", async () => {
    const emptyDb = new InMemoryEngineDb();
    emptyDb.seedSkills([skill()]); // skill exists; bank has nothing for it
    const emptyPorts = buildBrowserEngineAdapters({
      engineDb: emptyDb,
      questionSource: "bank",
    });
    await expect(
      openQuizItem(emptyPorts, { subject: SUBJECT, learnerId: LEARNER }),
    ).rejects.toThrow(/no reviewed question/);
  });
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

describe("runQuizSubmit — real elapsed_ms reaches the attempt (D0 timing plumbing)", () => {
  it("records the passed elapsedMs onto the attempt (not a fabricated 0)", async () => {
    const session = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    const result = await runQuizSubmit(ports, {
      session,
      question: question(),
      learnerId: LEARNER,
      letter: "B",
      elapsedMs: 4200,
      usedHint: false,
    });
    expect(result.attempt).not.toBeNull();
    expect(result.attempt?.elapsed_ms).toBe(4200);
  });
});

describe("runQuizSubmit — coach-session marker notify (ADR-0012 Amendment, FR-19)", () => {
  it("no selection ⇒ NO marker notify (failure path first)", async () => {
    const calls: string[] = [];
    const session = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    await runQuizSubmit(
      { ...ports, quizSubmitNotifier: { notifySubmitted: (q) => calls.push(q) } },
      {
        session,
        question: question(),
        learnerId: LEARNER,
        letter: null,
        elapsedMs: 1000,
        usedHint: false,
      },
    );
    expect(calls).toHaveLength(0);
  });

  it("a real submit fires the notifier once with the question id", async () => {
    const calls: string[] = [];
    const session = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    await runQuizSubmit(
      { ...ports, quizSubmitNotifier: { notifySubmitted: (q) => calls.push(q) } },
      {
        session,
        question: question(),
        learnerId: LEARNER,
        letter: "B",
        elapsedMs: 1000,
        usedHint: false,
      },
    );
    expect(calls).toEqual(["q1"]);
  });

  it("fire-and-forget: a throwing notifier never breaks the submit", async () => {
    const session = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    const result = await runQuizSubmit(
      {
        ...ports,
        quizSubmitNotifier: {
          notifySubmitted: () => {
            throw new Error("marker route down");
          },
        },
      },
      {
        session,
        question: question(),
        learnerId: LEARNER,
        letter: "B",
        elapsedMs: 1000,
        usedHint: false,
      },
    );
    expect(result.verdict?.correct).toBe(true);
    expect(result.attempt).not.toBeNull();
  });

  it("notifier fires even when a downstream port (scheduler.review) rejects", async () => {
    // Review finding A2: the learner HAS submitted once the answer is graded —
    // a failing FSRS review must not leave the coach in pre_submit forever
    // (feedback still renders answer fields client-side; the coach would
    // refuse to discuss them).
    const calls: string[] = [];
    const session = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    await expect(
      runQuizSubmit(
        {
          ...ports,
          scheduler: {
            ...ports.scheduler,
            review: () => Promise.reject(new Error("fsrs store down")),
          },
          quizSubmitNotifier: { notifySubmitted: (q) => calls.push(q) },
        },
        {
          session,
          question: question(),
          learnerId: LEARNER,
          letter: "B",
          elapsedMs: 1000,
          usedHint: false,
        },
      ),
    ).rejects.toThrow("fsrs store down");
    expect(calls).toEqual(["q1"]);
  });

  it("a bag without a notifier still submits (server/legacy path)", async () => {
    const session = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    const result = await runQuizSubmit(ports, {
      session,
      question: question(),
      learnerId: LEARNER,
      letter: "B",
      elapsedMs: 1000,
      usedHint: false,
    });
    expect(result.attempt).not.toBeNull();
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

describe("closeQuizSession — stores the tally the Summary reads (FR-D3/G1)", () => {
  it("writes score_correct/score_total + ended_at onto the session", async () => {
    const session = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    const closed = await closeQuizSession(ports, {
      sessionId: session.id,
      scoreCorrect: 3,
      scoreTotal: 5,
    });
    expect(closed.score_correct).toBe(3);
    expect(closed.score_total).toBe(5);
    expect(closed.ended_at).not.toBeNull();
    // The stored session — what Summary reads — carries the same tally.
    const stored = await ports.sessionRepo.get(session.id);
    expect(stored?.score_correct).toBe(3);
    expect(stored?.score_total).toBe(5);
  });

  it("is idempotent: re-closing re-applies the same tally without error", async () => {
    const session = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    await closeQuizSession(ports, { sessionId: session.id, scoreCorrect: 2, scoreTotal: 2 });
    const again = await closeQuizSession(ports, {
      sessionId: session.id,
      scoreCorrect: 2,
      scoreTotal: 2,
    });
    expect(again.score_correct).toBe(2);
    expect(again.score_total).toBe(2);
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

  it("returns an EMPTY ladder when the question has no reviewed rungs (FR-12)", async () => {
    db.seedHints([
      {
        id: "h-q1-1",
        subject: SUBJECT,
        question_id: "q1",
        rung: 1,
        body_md: "unreviewed generator draft",
        reviewed: false,
        generated_by: "gpt-4o-mini@run-9",
      },
    ]);
    const item = await openQuizItem(ports, { subject: SUBJECT, learnerId: LEARNER });
    expect(item.hintLadder).toEqual([]);
  });

  it("loads the question's reviewed hint ladder with the item (ADR-0014)", async () => {
    db.seedHints([
      {
        id: "h-q1-2",
        subject: SUBJECT,
        question_id: "q1",
        rung: 2,
        body_md: "conceptual rung",
        reviewed: true,
        generated_by: "authored",
      },
      {
        id: "h-q1-1b",
        subject: SUBJECT,
        question_id: "q1",
        rung: 1,
        body_md: "probe rung",
        reviewed: true,
        generated_by: "authored",
      },
    ]);
    const item = await openQuizItem(ports, { subject: SUBJECT, learnerId: LEARNER });
    expect(item.hintLadder.map((h) => h.body_md)).toEqual([
      "probe rung",
      "conceptual rung",
    ]);
  });
});
