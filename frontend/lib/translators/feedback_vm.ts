/**
 * feedback_vm — (Question, Verdict, Answer) → FeedbackVM (FR-E1..E5).
 *
 * Pure T1 map for the post-answer teaching screen (the core teaching moment).
 * It composes the ALREADY-COMPUTED grading `Verdict` (from the Grader — grading
 * never happens here) with the question's per-choice rationale into the view:
 *
 *   - banner: "celebrate" (FR-E2) when correct, "soft" (FR-E3) when wrong;
 *   - chosenRationale: THAT distractor's specific rationale (FR-E3) — never a
 *     generic message; correctRationale: the answer rationale (FR-E1);
 *   - reviewedChoices: each choice tagged with its per-state style
 *     (correct / chosen-wrong / other) for FR-E4;
 *   - ruleMd: the rule under test (FR-E1).
 *
 * Imports `wire/` only. No I/O, no React, no SDK.
 */

import type {
  Answer,
  AttemptResolution,
  Question,
  Verdict,
} from "../wire/engine_entities";

export type FeedbackBanner = "celebrate" | "soft" | "walked_through";

/** Per-choice review styling state (FR-E4). */
export type ReviewedChoiceState = "correct" | "chosen-wrong" | "other";

export interface ReviewedChoiceVM {
  readonly letter: string;
  readonly label: string;
  readonly state: ReviewedChoiceState;
}

export const WALKED_THROUGH_BANNER =
  "The breakdown takes it from here — this one won't count as solved.";

export const RESOLUTION_LABEL: Record<AttemptResolution, string> = {
  first_try: "Solved on first try",
  coached: "Worked through it with the coach",
  walked_through: "Walked through together",
};

export interface FeedbackVM {
  readonly correct: boolean;
  readonly banner: FeedbackBanner;
  readonly chosenLetter: string | null;
  readonly correctLetter: string | null;
  /** Rationale for the learner's chosen letter (FR-E3 distractor-specific / FR-E2). */
  readonly chosenRationale: string;
  /** Rationale for the correct letter — "Why A is correct" (FR-E1). */
  readonly correctRationale: string;
  readonly reviewedChoices: ReadonlyArray<ReviewedChoiceVM>;
  readonly ruleMd: string;
  /**
   * Sentence recap HTML (FR-E1 / FR-A7 / C5): `context_html` when it contains
   * `<u>` (view restyles to success); otherwise plain stem/context text with
   * no invented underline.
   */
  readonly recapHtml: string;
  readonly recapHasUnderline: boolean;
  /** Commit-first outcome label (FR-9); null under legacy / flag OFF. */
  readonly resultLabel: string | null;
  readonly resolution: AttemptResolution | null;
}

function stateFor(
  letter: string,
  correctLetter: string | null,
  chosenLetter: string | null,
): ReviewedChoiceState {
  if (letter === correctLetter) return "correct";
  if (letter === chosenLetter) return "chosen-wrong";
  return "other";
}

function stripHtmlTags(html: string): string {
  return html.replace(/<[^>]*>/g, "").trim();
}

/** Pure: build recap from context_html / stem without inventing a highlight. */
export function buildFeedbackRecap(question: Question): {
  readonly recapHtml: string;
  readonly recapHasUnderline: boolean;
} {
  const html = question.context_html ?? "";
  if (/<u[\s>]/i.test(html)) {
    return { recapHtml: html, recapHasUnderline: true };
  }
  const stem = question.stem?.trim() ?? "";
  if (stem.length > 0) {
    return { recapHtml: stem, recapHasUnderline: false };
  }
  return { recapHtml: stripHtmlTags(html), recapHasUnderline: false };
}

export function toFeedbackVM(
  question: Question,
  verdict: Verdict,
  answer: Answer,
  resolution?: AttemptResolution | null,
): FeedbackVM {
  const chosenLetter = answer.letter;
  const correctLetter = verdict.correct_letter ?? question.answer_letter;
  const rationale = question.per_choice_rationale;
  const recap = buildFeedbackRecap(question);
  const res = resolution ?? null;

  let banner: FeedbackBanner;
  if (res === "walked_through") {
    banner = "walked_through";
  } else if (verdict.correct) {
    banner = "celebrate";
  } else {
    banner = "soft";
  }

  // FBK-1: prefer authored why_correct / why_tempted; fall back to per-choice.
  const correctRationale =
    question.why_correct_md.trim() || (rationale[correctLetter] ?? "");
  const chosenRationale =
    res === "walked_through"
      ? question.why_tempted_md.trim() ||
        (chosenLetter && rationale[chosenLetter]) ||
        ""
      : (chosenLetter && rationale[chosenLetter]) || "";

  return {
    correct: verdict.correct,
    banner,
    chosenLetter,
    correctLetter,
    chosenRationale,
    correctRationale,
    reviewedChoices: question.choices.map((c) => ({
      letter: c.letter,
      label: c.label,
      // A correct learner's chosen row IS the correct row → "correct" wins
      // (stateFor checks correctLetter first), matching FR-E4.
      state: stateFor(c.letter, correctLetter, chosenLetter),
    })),
    ruleMd: question.rule_md,
    recapHtml: recap.recapHtml,
    recapHasUnderline: recap.recapHasUnderline,
    resultLabel: res != null ? RESOLUTION_LABEL[res] : null,
    resolution: res,
  };
}
