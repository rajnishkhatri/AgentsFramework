/**
 * useFeedback — the Feedback sub-state seam (FR-E1..E5).
 *
 * Feedback is a Quiz sub-state (plan §OD-5), not a route: after `runQuizSubmit`
 * returns a `Verdict`, this composes the pure `FeedbackVM` (via feedback_vm) and
 * the two post-answer actions — "Ask the coach" (routes to Coach with the item
 * in context, FR-E5) and "Next question →". Per F-R1 the component holds none of
 * this logic; it renders `buildFeedback(...)`'s output as props.
 *
 * `buildFeedback` is React-free (node-testable). `useFeedback` is a trivial
 * pass-through kept for symmetry with the other screen hooks.
 */

"use client";

import { toFeedbackVM, type FeedbackVM } from "@/lib/translators/feedback_vm";
import type { Answer, Question, Verdict } from "@/lib/wire/engine_entities";

/** Context handed to the Coach when "Ask the coach" is activated (FR-E5). */
export interface AskCoachContext {
  readonly questionId: string;
  readonly skillId: string;
}

interface FeedbackAbsent {
  readonly present: false;
}

interface FeedbackPresent {
  readonly present: true;
  readonly vm: FeedbackVM;
  readonly askCoachContext: AskCoachContext;
}

export type FeedbackState = FeedbackAbsent | FeedbackPresent;

export function buildFeedback(
  question: Question,
  verdict: Verdict | null,
  answer: Answer,
): FeedbackState {
  if (verdict == null) {
    // No verdict reached feedback (no selection, FR-D2a) — render nothing.
    return { present: false };
  }
  return {
    present: true,
    vm: toFeedbackVM(question, verdict, answer),
    askCoachContext: { questionId: question.id, skillId: question.skill_id },
  };
}

export function useFeedback(
  question: Question,
  verdict: Verdict | null,
  answer: Answer,
): FeedbackState {
  return buildFeedback(question, verdict, answer);
}
