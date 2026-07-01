/** Grader port (ADR-0006 #6) — pure, deterministic, verifier-first grading. */

import type {
  Answer,
  Question,
  Verdict,
} from "../../wire/engine_entities";

/**
 * Grader — pure, deterministic, verifier-first grading (ADR-0006 #6).
 *
 * Behavioral contract:
 *   1. PURE & SYNCHRONOUS. `grade()` has no I/O, no network, no clock — the
 *      same `(question, answer)` always yields the same `Verdict` (engine spec
 *      FR-C2). It is the React-OCP twin of the renderer registry: a new subject
 *      is a NEW Grader adapter, never an edit here.
 *   2. SYNC RETURN (P5 exception). Unlike the other engine ports, `grade()`
 *      returns `Verdict` directly, not `Promise<Verdict>`. Grading is pure
 *      computation called inline at feedback time and on the generation
 *      self-consistency gate (FR-E2); making it async would add a needless
 *      microtask and defeat its reuse as a synchronous verifier. This
 *      synchronicity is the documented P5 exception for this port.
 *   3. VERIFIER-FIRST. English = exact-letter-match. A future symbolic/numeric
 *      grader implements the SAME interface with canonicalization; an LLM, if
 *      ever used, sits BEHIND a deterministic verifier, never in front of the
 *      learner-facing verdict (FR-C4).
 *   4. NO SELECTION ⇒ NO VERDICT (FR-D2a). If `answer.letter` is null (nothing
 *      selected), `grade()` returns `null` — the caller records no attempt and
 *      shows no feedback. A non-null letter always yields a `Verdict`.
 *   5. INCORRECT ⇒ two rationale handles (FR-C3): the verdict's `rationale_key`
 *      points at the distractor rationale; the correct-answer rationale is
 *      reachable via `correct_letter`. CORRECT ⇒ celebrate state (FR-C3a):
 *      `correct = true` + `correct_letter` set.
 *
 * Pure: no `@throws` — invalid input yields a `Verdict` or `null`, never an
 * exception (a malformed question is a generation-time concern, gated upstream).
 */
export interface Grader {
  /**
   * Grade an answer against a question. Returns `null` when no letter is
   * selected (FR-D2a); otherwise a deterministic `Verdict`. Synchronous and
   * pure (P5 exception — see contract above).
   */
  grade(question: Question, answer: Answer): Verdict | null;
}
