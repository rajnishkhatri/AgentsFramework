/**
 * feedback_vm — (Question, Verdict, Answer) → FeedbackVM (FR-E1..E5 / T22–T23).
 *
 * Pure T1 map for the post-answer teaching screen (the core teaching moment).
 * It composes the ALREADY-COMPUTED grading `Verdict` (from the Grader — grading
 * never happens here) with the question's per-choice rationale into the view:
 *
 *   - banner: "celebrate" (FR-E2) when correct, "soft" (FR-E3) when wrong;
 *   - chosenRationale: THAT distractor's specific rationale (FR-E3) — never a
 *     generic message; correctRationale: the answer rationale (FR-E1);
 *   - reviewedChoices: each choice tagged with its per-state style
 *     (correct / chosen-wrong / other) for FR-E4 + per-choice rationale (V17);
 *   - feedCards: FEED-UP / FEED-BACK / FEED-FORWARD triplet (V16);
 *   - procedureSteps: numbered steps from rule_md when authored that way (V19);
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

export type FeedCardKind = "up" | "back" | "forward";

export interface FeedCardVM {
  readonly kind: FeedCardKind;
  readonly eyebrow: string;
  readonly body: string;
}

export interface ReviewedChoiceVM {
  readonly letter: string;
  readonly label: string;
  readonly state: ReviewedChoiceState;
  /** Per-choice rationale (V17); empty string when the bank left it blank. */
  readonly rationale: string;
}

/** Legacy cost-only copy — kept for call sites that still quote the constant. */
export const WALKED_THROUGH_BANNER =
  "The breakdown takes it from here — this one won't count as solved.";

/**
 * V14 / T22: walked-through banner delivers the answer + last pick.
 * This is where the no-reveal coaching contract pays off — the chat never
 * named the key; the breakdown does.
 */
export function composeWalkedThroughBanner(
  correctLetter: string,
  lastPick: string | null,
): string {
  const pick = lastPick ?? "?";
  return `The answer appears here, not in the chat: it's ${correctLetter}. Your last pick was ${pick} — the cards below unpack both.`;
}

export const RESOLUTION_LABEL: Record<AttemptResolution, string> = {
  first_try: "Solved on first try",
  coached: "Worked through it with the coach",
  walked_through: "Walked through together",
};

export interface FeedbackVMOptions {
  /** Joined skill display name; omit/null → goal card avoids fabricating a label. */
  readonly skillName?: string | null;
}

export interface FeedbackVM {
  readonly correct: boolean;
  readonly banner: FeedbackBanner;
  /** Learner-facing banner copy (composed — walked-through includes letters). */
  readonly bannerText: string;
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
  /** V16 feed-up / feed-back / feed-forward triplet. */
  readonly feedCards: ReadonlyArray<FeedCardVM>;
  /**
   * V19: numbered decision procedure parsed from `rule_md`, or null when the
   * rule is a single prose sentence (AP-6 — don't invent steps).
   */
  readonly procedureSteps: ReadonlyArray<string> | null;
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

/** Parse "1. … / 2. …" lists from rule_md; require ≥2 steps or return null. */
export function parseProcedureSteps(
  ruleMd: string,
): ReadonlyArray<string> | null {
  const steps: string[] = [];
  for (const line of ruleMd.split(/\r?\n/)) {
    const m = line.trim().match(/^\d+[\.\)]\s+(.+)$/);
    if (m?.[1]) steps.push(m[1].trim());
  }
  return steps.length >= 2 ? steps : null;
}

function composeFeedCards(
  question: Question,
  chosenLetter: string | null,
  chosenRationale: string,
  skillName: string | null | undefined,
): ReadonlyArray<FeedCardVM> {
  const skill =
    skillName != null && skillName.trim().length > 0
      ? skillName.trim()
      : null;
  const upBody = skill
    ? `${skill} · ${question.item_type.replace(/-/g, " ")}. Mastering this is part of lifting ${skill}.`
    : `${question.item_type.replace(/-/g, " ")}. Keep working the pattern this item tests.`;

  const mc = question.misconception?.trim() ?? "";
  const tempted = question.why_tempted_md.trim();
  let backBody =
    mc ||
    tempted ||
    chosenRationale ||
    "This distractor looked plausible — the cards below unpack why.";
  if (chosenLetter != null && (mc || tempted)) {
    backBody = `${backBody} Your last pick, ${chosenLetter}, is the classic version of that trap.`;
  }

  const rule = question.rule_md.trim();
  const forwardBody = rule
    ? `Your move next time. ${rule}`
    : "Your move next time. Re-apply the same test on the next item.";

  return [
    { kind: "up", eyebrow: "FEED-UP · GOAL", body: upBody },
    { kind: "back", eyebrow: "FEED-BACK · GAP", body: backBody },
    { kind: "forward", eyebrow: "FEED-FORWARD · NEXT", body: forwardBody },
  ];
}

export function toFeedbackVM(
  question: Question,
  verdict: Verdict,
  answer: Answer,
  resolution?: AttemptResolution | null,
  opts?: FeedbackVMOptions,
): FeedbackVM {
  const chosenLetter = answer.letter;
  const correctLetter = verdict.correct_letter ?? question.answer_letter;
  const rationale = question.per_choice_rationale;
  const recap = buildFeedbackRecap(question);
  const res = resolution ?? null;

  let banner: FeedbackBanner;
  let bannerText: string;
  if (res === "walked_through") {
    banner = "walked_through";
    bannerText = composeWalkedThroughBanner(correctLetter, chosenLetter);
  } else if (verdict.correct) {
    banner = "celebrate";
    bannerText = "Exactly right.";
  } else {
    banner = "soft";
    bannerText = "Not quite — and that's useful.";
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
    bannerText,
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
      rationale: (rationale[c.letter] ?? "").trim(),
    })),
    ruleMd: question.rule_md,
    recapHtml: recap.recapHtml,
    recapHasUnderline: recap.recapHasUnderline,
    resultLabel: res != null ? RESOLUTION_LABEL[res] : null,
    resolution: res,
    feedCards: composeFeedCards(
      question,
      chosenLetter,
      chosenRationale,
      opts?.skillName,
    ),
    procedureSteps: parseProcedureSteps(question.rule_md),
  };
}
