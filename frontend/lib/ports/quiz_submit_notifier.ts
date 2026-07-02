/**
 * QuizSubmitNotifier — fire-and-forget submit signal (ADR-0012 Amendment).
 *
 * Carries the quiz-submit fact to the coach-session marker store so the
 * coach BFF can derive post_feedback mode for that item (FR-19/FR-21).
 *
 * Behavioral contract:
 *   1. FIRE-AND-FORGET — `notifySubmitted` is deliberately synchronous
 *      (P5 sync exception): it returns void, never a promise the submit
 *      path awaits; a failed write must never delay or break grading. A
 *      missed marker fails CLOSED (the coach stays pre_submit and
 *      over-strips — annoying, never leaking).
 *   2. The adapter sends ONLY `question_id`; the learner identity is the
 *      server-derived session subject on the receiving route (S3).
 */
export interface QuizSubmitNotifier {
  notifySubmitted(questionId: string): void;
}
