/**
 * Phase 0.5 — quiz_item_vm (FR-D2/A6/D4, L2 contract, TAP-2 table-driven).
 *
 * Pure map: Question → QuizItemVM for the quiz item column — the context
 * sentence carrying the underlined span (FR-A6), the stem, and the choice rows
 * (choice A is "NO CHANGE", FR-D2). Also exposes the pure submit-gate
 * (FR-D4/D2a): no selection ⇒ submit disabled.
 *
 * Failure/edge rows first (Anti-Pattern 6): the no-selection gate (submit
 * disabled) BEFORE the happy path.
 */

import { describe, expect, it } from "vitest";
import { toQuizItemVM, canSubmit } from "./quiz_item_vm";
import type { Question } from "../wire/engine_entities";

function question(over: Partial<Question> = {}): Question {
  return {
    id: "q1",
    subject: "act-english",
    skill_id: "s-punc",
    difficulty: 3,
    context_html: 'The committee <span class="u">have</span> decided.',
    stem: "Which choice is best?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "has", is_no_change: false },
      { letter: "C", label: "having", is_no_change: false },
      { letter: "D", label: "had", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: { A: "…", B: "…" },
    why_correct_md: "…",
    why_tempted_md: "…",
    rule_md: "…",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

describe("canSubmit — FR-D4/D2a (failure path first)", () => {
  it("no selection (null) ⇒ submit disabled", () => {
    expect(canSubmit(null)).toBe(false);
  });
  it("empty string ⇒ submit disabled", () => {
    expect(canSubmit("")).toBe(false);
  });
  it("a selected letter ⇒ submit enabled", () => {
    expect(canSubmit("A")).toBe(true);
  });
});

describe("toQuizItemVM — happy path", () => {
  it("carries the context html (underlined span) and stem verbatim (FR-A6/D2)", () => {
    const vm = toQuizItemVM(question());
    expect(vm.contextHtml).toContain('class="u"');
    expect(vm.stem).toBe("Which choice is best?");
    expect(vm.questionId).toBe("q1");
  });

  it("renders four choice rows with A = NO CHANGE (FR-D2)", () => {
    const vm = toQuizItemVM(question());
    expect(vm.choices).toHaveLength(4);
    expect(vm.choices[0]).toMatchObject({ letter: "A", label: "NO CHANGE", isNoChange: true });
    expect(vm.choices[1]).toMatchObject({ letter: "B", isNoChange: false });
  });

  it("does NOT leak the answer letter into the VM (FR-D5 non-reveal)", () => {
    const vm = toQuizItemVM(question({ answer_letter: "B" }));
    // The item VM feeds the pre-answer screen; the correct letter must not ride it.
    expect(JSON.stringify(vm)).not.toContain('"answer_letter"');
    expect((vm as unknown as Record<string, unknown>).answerLetter).toBeUndefined();
  });
});
