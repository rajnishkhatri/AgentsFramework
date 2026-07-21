/**
 * Phase 0.5 — feedback_vm (FR-E1..E5, L2 contract, TAP-2 table-driven).
 *
 * Pure map: (Question, Verdict, Answer) → FeedbackVM for the post-answer
 * teaching screen. The named failure row runs FIRST (plan §Phase 0.5): a WRONG
 * pick (FR-E3) must surface the soft banner AND *that distractor's* specific
 * rationale, plus the correct-answer rationale — never a generic message.
 *
 * Then the correct-pick celebrate path (FR-E2), the per-choice review styling
 * states (FR-E4), and the rule under test (FR-E1).
 */

import { describe, expect, it } from "vitest";
import { toFeedbackVM } from "./feedback_vm";
import type { Answer, Question, Verdict } from "../wire/engine_entities";

function question(over: Partial<Question> = {}): Question {
  return {
    id: "q1",
    subject: "act-english",
    skill_id: "s-punc",
    difficulty: 3,
    context_html: "The committee <u>have</u> decided.",
    stem: "Which choice is best?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "has", is_no_change: false },
      { letter: "C", label: "having", is_no_change: false },
      { letter: "D", label: "had", is_no_change: false },
    ],
    answer_letter: "A",
    per_choice_rationale: {
      A: "A is correct: singular collective noun → singular verb.",
      B: "B tempted you: 'committee' sounds plural but is singular.",
      C: "C is a participle, not a finite verb.",
      D: "D shifts the tense wrongly.",
    },
    why_correct_md: "Singular collective noun → singular verb.",
    why_tempted_md: "'committee' sounds plural.",
    rule_md: "Collective nouns are singular.",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

describe("toFeedbackVM — wrong pick (FR-E3, failure path first)", () => {
  const q = question({ answer_letter: "A" });
  const verdict: Verdict = {
    correct: false,
    correct_letter: "A",
    rationale_key: "B",
  };
  const answer: Answer = { letter: "B" };

  it("shows the soft (not-quite) banner, not the celebrate banner", () => {
    const vm = toFeedbackVM(q, verdict, answer);
    expect(vm.correct).toBe(false);
    expect(vm.banner).toBe("soft");
  });

  it("surfaces THAT distractor's specific rationale (B), plus the correct one (A)", () => {
    const vm = toFeedbackVM(q, verdict, answer);
    expect(vm.chosenRationale).toContain("B tempted you");
    // FBK-1: authored why_correct_md wins over per_choice for the key.
    expect(vm.correctRationale).toContain("Singular collective noun");
  });

  it("marks the chosen letter and the correct letter", () => {
    const vm = toFeedbackVM(q, verdict, answer);
    expect(vm.chosenLetter).toBe("B");
    expect(vm.correctLetter).toBe("A");
  });
});

describe("toFeedbackVM — correct pick (FR-E2 celebrate)", () => {
  const q = question({ answer_letter: "A" });
  const verdict: Verdict = {
    correct: true,
    correct_letter: "A",
    rationale_key: "A",
  };
  const answer: Answer = { letter: "A" };

  it("shows the celebrate banner", () => {
    const vm = toFeedbackVM(q, verdict, answer);
    expect(vm.correct).toBe(true);
    expect(vm.banner).toBe("celebrate");
  });
});

describe("toFeedbackVM — per-choice review states (FR-E4) + rule (FR-E1)", () => {
  const q = question({ answer_letter: "A" });
  const verdict: Verdict = {
    correct: false,
    correct_letter: "A",
    rationale_key: "B",
  };
  const answer: Answer = { letter: "B" };
  const vm = toFeedbackVM(q, verdict, answer);

  it("styles the correct choice as 'correct', the chosen-wrong as 'chosen-wrong', others 'other'", () => {
    const byLetter = Object.fromEntries(
      vm.reviewedChoices.map((c) => [c.letter, c.state]),
    );
    expect(byLetter.A).toBe("correct");
    expect(byLetter.B).toBe("chosen-wrong");
    expect(byLetter.C).toBe("other");
    expect(byLetter.D).toBe("other");
  });

  it("carries the rule under test (FR-E1)", () => {
    expect(vm.ruleMd).toBe("Collective nouns are singular.");
  });

  it("when the learner is correct, the chosen row is styled 'correct' (not chosen-wrong)", () => {
    const cq = question({ answer_letter: "A" });
    const cVm = toFeedbackVM(
      cq,
      { correct: true, correct_letter: "A", rationale_key: "A" },
      { letter: "A" },
    );
    const a = cVm.reviewedChoices.find((c) => c.letter === "A");
    expect(a?.state).toBe("correct");
  });
});

describe("toFeedbackVM — green-span recap (BP-2c / FR-7 / C5)", () => {
  it("keeps <u> in recapHtml when context_html has an underlined span", () => {
    const vm = toFeedbackVM(
      question(),
      { correct: true, correct_letter: "A", rationale_key: "A" },
      { letter: "A" },
    );
    expect(vm.recapHtml).toContain("<u>");
    expect(vm.recapHtml).toContain("have");
    expect(vm.recapHasUnderline).toBe(true);
  });

  it("falls back to plain stem without inventing <u> when context has none", () => {
    const vm = toFeedbackVM(
      question({
        context_html: "Plain sentence with no underline.",
        stem: "Which is best?",
      }),
      { correct: true, correct_letter: "A", rationale_key: "A" },
      { letter: "A" },
    );
    expect(vm.recapHtml).toBe("Which is best?");
    expect(vm.recapHtml).not.toContain("<u>");
    expect(vm.recapHasUnderline).toBe(false);
  });

  it("falls back to context text when no <u> and stem is empty", () => {
    const vm = toFeedbackVM(
      question({ context_html: "Just a sentence.", stem: "" }),
      { correct: true, correct_letter: "A", rationale_key: "A" },
      { letter: "A" },
    );
    expect(vm.recapHtml).toBe("Just a sentence.");
    expect(vm.recapHasUnderline).toBe(false);
  });

  it("fully strips nested/partial tags on the stripHtmlTags fallback (no re-formed <script> — CodeQL js/incomplete-multi-character-sanitization)", () => {
    // A one-shot `.replace(/<[^>]*>/g, "")` leaves a re-formed `<script>` behind:
    // removing the inner `<script>` from `<scr<script>ipt>alert(1)` collapses the
    // outer fragments into a fresh `<script>`. The fixpoint loop must remove it.
    const vm = toFeedbackVM(
      question({
        context_html: "<scr<script>ipt>alert(1)</scr</script>ipt>",
        stem: "",
      }),
      { correct: true, correct_letter: "A", rationale_key: "A" },
      { letter: "A" },
    );
    expect(vm.recapHtml).not.toMatch(/<script/i);
    expect(vm.recapHtml).not.toContain("<");
    expect(vm.recapHtml).not.toContain(">");
  });
});

describe("toFeedbackVM — commit-first resolution labels (FR-6/9)", () => {
  const q = question({ answer_letter: "A" });

  it("first_try → celebrate + Solved on first try", () => {
    const vm = toFeedbackVM(
      q,
      { correct: true, correct_letter: "A" },
      { letter: "A" },
      "first_try",
    );
    expect(vm.banner).toBe("celebrate");
    expect(vm.resultLabel).toBe("Solved on first try");
  });

  it("coached → celebrate + Worked through it with the coach", () => {
    const vm = toFeedbackVM(
      q,
      { correct: true, correct_letter: "A" },
      { letter: "A" },
      "coached",
    );
    expect(vm.resultLabel).toBe("Worked through it with the coach");
  });

  it("walked_through → walked banner + why-tempted keyed to last wrong letter", () => {
    const vm = toFeedbackVM(
      q,
      { correct: false, correct_letter: "A" },
      { letter: "B" },
      "walked_through",
    );
    expect(vm.banner).toBe("walked_through");
    expect(vm.resultLabel).toBe("Walked through together");
    expect(vm.chosenLetter).toBe("B");
    // V14: banner delivers answer + last pick (not cost-only).
    expect(vm.bannerText).toMatch(/it's A/);
    expect(vm.bannerText).toMatch(/last pick was B/);
    // FBK-1 walked-through: why_tempted_md for the last wrong letter's gap.
    expect(vm.chosenRationale).toContain("committee");
  });
});

describe("toFeedbackVM — T23 composition (V16–V19)", () => {
  it("builds feed-up / feed-back / feed-forward cards from sourced fields (V16)", () => {
    const vm = toFeedbackVM(
      question({
        misconception: "Learners match the verb to the nearest noun.",
        why_tempted_md: "Nearest-noun trap.",
        rule_md: "Find the verb. Ask who or what does it.",
      }),
      { correct: false, correct_letter: "A" },
      { letter: "B" },
      "walked_through",
      { skillName: "Usage" },
    );
    expect(vm.feedCards.map((c) => c.kind)).toEqual(["up", "back", "forward"]);
    expect(vm.feedCards[0]!.body).toContain("Usage");
    expect(vm.feedCards[1]!.body).toContain("nearest noun");
    expect(vm.feedCards[2]!.body).toMatch(/Find the verb/i);
  });

  it("attaches per-choice rationales for every choice (V17)", () => {
    const vm = toFeedbackVM(
      question(),
      { correct: false, correct_letter: "A" },
      { letter: "B" },
    );
    expect(vm.reviewedChoices).toHaveLength(4);
    for (const c of vm.reviewedChoices) {
      expect(c.rationale.length).toBeGreaterThan(0);
    }
    expect(
      vm.reviewedChoices.find((c) => c.letter === "C")?.rationale,
    ).toContain("participle");
  });

  it("parses numbered procedure steps from rule_md when present (V19)", () => {
    const vm = toFeedbackVM(
      question({
        rule_md:
          "1. Find the verb.\n2. Ask who or what does it.\n3. Match the verb to that head.",
      }),
      { correct: true, correct_letter: "A" },
      { letter: "A" },
    );
    expect(vm.procedureSteps).toEqual([
      "Find the verb.",
      "Ask who or what does it.",
      "Match the verb to that head.",
    ]);
  });

  it("leaves procedureSteps null when rule_md is a single prose sentence", () => {
    const vm = toFeedbackVM(
      question({ rule_md: "Collective nouns are singular." }),
      { correct: true, correct_letter: "A" },
      { letter: "A" },
    );
    expect(vm.procedureSteps).toBeNull();
  });
});

describe("toFeedbackVM — feed-up item-type label hygiene (Phase-3 residual R5)", () => {
  it("humanizes item_type in the goal card (no raw 'mc' token)", () => {
    const vm = toFeedbackVM(
      question(),
      { correct: false, correct_letter: "A", rationale_key: "B" },
      { letter: "B" },
      null,
      { skillName: "Punctuation" },
    );
    const up = vm.feedCards[0]!;
    expect(up.body).toContain("underlined-span item");
    expect(up.body).not.toMatch(/\bmc\b/i);
  });

  it("humanizes item_type without a skill name too", () => {
    const vm = toFeedbackVM(
      question(),
      { correct: false, correct_letter: "A", rationale_key: "B" },
      { letter: "B" },
    );
    expect(vm.feedCards[0]!.body).not.toMatch(/\bmc\b/i);
  });
});
