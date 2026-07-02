/**
 * useQuiz — the Quiz screen's seam onto the engine ports (FR-D1..D8).
 *
 * Per F-R1 the Quiz component owns NO domain logic. The whole learning
 * sequence — scheduler pick → reviewed question → grade → record attempt →
 * FSRS review — lives here. The orchestration is exported as React-free async
 * functions (`openQuizItem`, `runQuizSubmit`) so it is testable in node against
 * a seeded InMemoryEngineDb with no React and no mocks (the analogue of
 * `consumeRunStream` in use_agent_run).
 *
 * Grading order (FR-D2/D3/A2): grade with the pure Grader FIRST; only a
 * non-null verdict (a real selection, FR-D2a) yields an attempt, which is then
 * recorded (AttemptRepo) and fed to the Scheduler's `review()` — the sole
 * `skill_state` writer. No selection ⇒ no verdict ⇒ no attempt ⇒ no state write.
 *
 * Imports engine ports (via the injected bag) + wire shapes only. The default
 * bag comes from `useEngine()` context (C3); tests inject a seeded bag directly.
 */

"use client";

import * as React from "react";
import type { EnginePortBag } from "@/lib/composition_engine";
import { useEngine } from "@/app/engine-provider";
import type {
  Attempt,
  Question,
  QuizSession,
  SessionMode,
  SkillState,
  Verdict,
} from "@/lib/wire/engine_entities";

export interface QuizItemResult {
  readonly skillId: string;
  readonly question: Question;
}

export interface OpenSessionArgs {
  readonly subject: string;
  readonly learnerId: string;
  readonly mode: SessionMode;
  /** Skill id for a drill session (FR-A5); omit/null for adaptive/review. */
  readonly focus?: string | null;
}

export interface QuizSessionResult {
  readonly session: QuizSession;
  /**
   * The learner's per-skill mastery captured ONCE at session open, before the
   * first `review()` mutates skill_state — the "before" half of the FR-G1 delta
   * (ADR-0011 §4). Keyed by `skill_id`; empty for a brand-new learner (delta
   * later renders "—"). Immutable: it must not track the in-session mutations
   * the Scheduler makes, so Summary can diff it against a fresh read.
   */
  readonly skillStateAtStart: ReadonlyMap<string, SkillState>;
}

/**
 * Open a quiz session and snapshot the learner's mastery at that moment.
 *
 * FR-G1 needs the mastery delta across the session. `SkillState.mastery` is
 * mutated by `Scheduler.review()` during play, so "before" must be read once at
 * open — after `sessionRepo.open(...)` resolves, before any `runQuizSubmit`
 * (ADR-0011 §4). The read goes through the read-only `learnerRead` port, never
 * the write path (FR-A2: the Scheduler is the sole skill_state writer).
 */
export async function openQuizSession(
  ports: EnginePortBag,
  args: OpenSessionArgs,
): Promise<QuizSessionResult> {
  const session = await ports.sessionRepo.open(
    args.subject,
    args.learnerId,
    args.mode,
    args.focus ?? null,
  );
  const rows = await ports.learnerRead.listSkillState(args.subject, args.learnerId);
  const skillStateAtStart = new Map(rows.map((s) => [s.skill_id, s]));
  return { session, skillStateAtStart };
}

/** Pick the next (skill, question) for the learner and load the reviewed item. */
export async function openQuizItem(
  ports: EnginePortBag,
  args: { subject: string; learnerId: string },
): Promise<QuizItemResult> {
  const next = await ports.scheduler.next(args.subject, args.learnerId);
  const question = await ports.questionRepo.get(next.question_id);
  if (question == null) {
    // The scheduler picked an id the repo can't resolve — a seam defect, surfaced
    // rather than handing the learner an empty item.
    throw new Error(`scheduled question ${next.question_id} not found`);
  }
  return { skillId: next.skill_id, question };
}

export interface QuizSubmitArgs {
  readonly session: QuizSession;
  readonly question: Question;
  readonly learnerId: string;
  readonly letter: string | null;
  readonly elapsedMs: number;
  readonly usedHint: boolean;
}

export interface QuizSubmitResult {
  /** null when nothing was selected (FR-D2a). */
  readonly verdict: Verdict | null;
  /** null when nothing was selected (no attempt recorded). */
  readonly attempt: Attempt | null;
  /** null when nothing was selected (no FSRS review ran). */
  readonly skillState: SkillState | null;
}

/**
 * Grade → (record + review) for one submitted answer. No selection ⇒ all-null
 * result and zero side effects (FR-D2a/D4).
 */
export async function runQuizSubmit(
  ports: EnginePortBag,
  args: QuizSubmitArgs,
): Promise<QuizSubmitResult> {
  const verdict = ports.grader.grade(args.question, { letter: args.letter });
  if (verdict == null || args.letter == null) {
    // FR-D2a: nothing selected — record nothing, schedule nothing.
    return { verdict: null, attempt: null, skillState: null };
  }

  const attempt = await ports.attemptRepo.record({
    subject: args.question.subject,
    session_id: args.session.id,
    question_id: args.question.id,
    chosen_letter: args.letter,
    correct: verdict.correct,
    elapsed_ms: args.elapsedMs,
    used_hint: args.usedHint,
  });

  const skillState = await ports.scheduler.review(attempt);

  // ADR-0012 Amendment (FR-19): fire-and-forget marker write — flips the
  // coach's derived mode to post_feedback for this item. Only a REAL submit
  // notifies (the no-selection path returned above); a throwing notifier
  // never breaks grading (fail-closed: the coach just stays pre_submit).
  try {
    ports.quizSubmitNotifier?.notifySubmitted(args.question.id);
  } catch {
    // Swallow by contract (QuizSubmitNotifier rule 1).
  }

  return { verdict, attempt, skillState };
}

export interface CloseSessionArgs {
  readonly sessionId: string;
  readonly scoreCorrect: number;
  readonly scoreTotal: number;
}

/**
 * Close the session with the running tally so the STORED score is what the
 * Summary reads (FR-D3/G1 — Summary never re-tallies). Called once on Finish,
 * before the route change. `sessionRepo.close` is idempotent, so a late/duplicate
 * close (e.g. a double-tap) re-applies the same tally harmlessly.
 */
export async function closeQuizSession(
  ports: EnginePortBag,
  args: CloseSessionArgs,
): Promise<QuizSession> {
  return ports.sessionRepo.close(args.sessionId, {
    score_correct: args.scoreCorrect,
    score_total: args.scoreTotal,
  });
}

/**
 * Thin React wrapper: reads the engine bag from context (C3) and exposes the
 * orchestration bound to it. The component calls these; it holds no port logic.
 * Tests exercise `openQuizItem` / `runQuizSubmit` / `closeQuizSession` directly
 * with an injected bag, so the hook itself stays a trivial context binding (no
 * test-only param that would force a conditional `useEngine()` call).
 */
export function useQuiz(): {
  openSession: (args: OpenSessionArgs) => Promise<QuizSessionResult>;
  openItem: (args: { subject: string; learnerId: string }) => Promise<QuizItemResult>;
  submit: (args: QuizSubmitArgs) => Promise<QuizSubmitResult>;
  closeSession: (args: CloseSessionArgs) => Promise<QuizSession>;
} {
  const ports = useEngine();
  return React.useMemo(
    () => ({
      openSession: (args: OpenSessionArgs) => openQuizSession(ports, args),
      openItem: (args: { subject: string; learnerId: string }) =>
        openQuizItem(ports, args),
      submit: (args: QuizSubmitArgs) => runQuizSubmit(ports, args),
      closeSession: (args: CloseSessionArgs) => closeQuizSession(ports, args),
    }),
    [ports],
  );
}
