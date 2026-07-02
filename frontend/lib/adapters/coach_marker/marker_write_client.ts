/**
 * Browser-side QuizSubmitNotifier adapter (ADR-0012 Amendment).
 *
 * POSTs `{question_id}` to `/api/coach/session-marker` fire-and-forget: the
 * promise is detached and every failure is swallowed (a missed marker fails
 * CLOSED to pre_submit — the coach over-strips, never leaks). No PII in the
 * body; the learner identity is the HttpOnly session cookie the route
 * verifies server-side (S3).
 *
 * A5 note: there is deliberately no error translation table — this adapter
 * has no caller-visible failure surface by contract (port rule 1).
 */

import type { QuizSubmitNotifier } from "@/lib/ports/quiz_submit_notifier";

export class FetchQuizSubmitNotifier implements QuizSubmitNotifier {
  constructor(
    private readonly fetchImpl: typeof fetch | null = typeof fetch !==
    "undefined"
      ? fetch.bind(globalThis)
      : null,
  ) {}

  notifySubmitted(questionId: string): void {
    if (!this.fetchImpl) return; // non-browser context: no-op
    try {
      void this.fetchImpl("/api/coach/session-marker", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question_id: questionId }),
      }).catch(() => {
        // Swallow: fail-closed contract — the coach derives pre_submit.
      });
    } catch {
      // Synchronous throw (e.g. relative URL outside a browser): same
      // fail-closed posture — never let a marker write break a submit.
    }
  }
}
