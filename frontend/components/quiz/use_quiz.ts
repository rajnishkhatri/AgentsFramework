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
  SkillState,
  Verdict,
} from "@/lib/wire/engine_entities";

export interface QuizItemResult {
  readonly skillId: string;
  readonly question: Question;
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

  return { verdict, attempt, skillState };
}

/**
 * Thin React wrapper: reads the engine bag from context (C3) and exposes the
 * orchestration bound to it. The component calls these; it holds no port logic.
 * Tests exercise `openQuizItem` / `runQuizSubmit` directly with an injected bag,
 * so the hook itself stays a trivial context binding (no test-only param that
 * would force a conditional `useEngine()` call).
 */
export function useQuiz(): {
  openItem: (args: { subject: string; learnerId: string }) => Promise<QuizItemResult>;
  submit: (args: QuizSubmitArgs) => Promise<QuizSubmitResult>;
} {
  const ports = useEngine();
  return React.useMemo(
    () => ({
      openItem: (args: { subject: string; learnerId: string }) =>
        openQuizItem(ports, args),
      submit: (args: QuizSubmitArgs) => runQuizSubmit(ports, args),
    }),
    [ports],
  );
}
