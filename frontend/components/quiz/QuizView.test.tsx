/**
 * Phase 1.4 — QuizView SSR structural tests (FR-D2/D3/D4/D5/A6, L1 jsdom).
 *
 * Repo convention: renderToStaticMarkup + JSDOM (no RTL). Selection is driven by
 * a `selectedLetter` prop (the hook owns the state — F-R1), so the two states
 * (nothing selected / a choice selected) are both SSR-renderable and the
 * submit-gate invariant is assertable without a click.
 *
 * Failure/edge first: with no selection, Submit is disabled (FR-D4); the hint,
 * when shown, must NOT contain the answer letter (FR-D5).
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QuizView } from "./QuizView";
import { toQuizItemVM } from "@/lib/translators/quiz_item_vm";
import type { Question } from "@/lib/wire/engine_entities";

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

function render(props: {
  selectedLetter?: string | null;
  hintOpen?: boolean;
  hint?: string;
}): Document {
  const vm = toQuizItemVM(question());
  const html = renderToStaticMarkup(
    React.createElement(QuizView, {
      vm,
      selectedLetter: props.selectedLetter ?? null,
      onSelect: () => {},
      onSubmit: () => {},
      hintOpen: props.hintOpen ?? false,
      hint: props.hint ?? "What does 'committee' act as here — one body or many?",
      onToggleHint: () => {},
    }),
  );
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

describe("QuizView — no selection (edge first, FR-D4)", () => {
  const doc = render({ selectedLetter: null });

  it("Submit is disabled while nothing is selected", () => {
    const submit = doc.querySelector('[data-testid="quiz-submit"]');
    expect(submit?.hasAttribute("disabled")).toBe(true);
  });

  it("renders four choice rows with A = NO CHANGE (FR-D2)", () => {
    expect(doc.querySelectorAll('[data-testid^="choice-"]')).toHaveLength(4);
    expect(doc.querySelector('[data-testid="choice-A"]')?.textContent).toContain("NO CHANGE");
  });

  it("carries the underlined-span context html (FR-A6)", () => {
    expect(doc.querySelector('[data-testid="quiz-context"]')?.innerHTML).toContain('class="u"');
  });
});

describe("QuizView — a choice selected (FR-D3)", () => {
  const doc = render({ selectedLetter: "B" });

  it("marks the selected row and enables Submit", () => {
    expect(doc.querySelector('[data-testid="choice-B"]')?.getAttribute("data-selected")).toBe("true");
    expect(doc.querySelector('[data-testid="quiz-submit"]')?.hasAttribute("disabled")).toBe(false);
  });

  it("only the selected row is marked (prior selection cleared)", () => {
    expect(doc.querySelector('[data-testid="choice-A"]')?.getAttribute("data-selected")).toBe("false");
  });
});

describe("QuizView — hint never reveals the answer (FR-D5)", () => {
  it("the open hint card contains the Socratic prompt but NOT the answer letter", () => {
    const doc = render({ selectedLetter: null, hintOpen: true });
    const hint = doc.querySelector('[data-testid="quiz-hint"]');
    expect(hint).not.toBeNull();
    // The answer is B; the Socratic hint must not name it as the answer.
    expect(hint?.textContent).not.toMatch(/answer is\s*B/i);
    expect(hint?.textContent).toContain("committee");
  });

  it("hint is hidden when closed", () => {
    const doc = render({ selectedLetter: null, hintOpen: false });
    expect(doc.querySelector('[data-testid="quiz-hint"]')).toBeNull();
  });
});
