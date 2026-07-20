/**
 * Phase 1.5 — FeedbackView SSR structural tests (FR-E1/E4/A8, L1 jsdom).
 *
 * Repo convention (no @testing-library/react): renderToStaticMarkup + JSDOM.
 * Failure/edge first: a wrong-pick verdict must show the SOFT banner and style
 * the chosen-wrong row distinctly — AND never convey state by color alone
 * (FR-A8: each reviewed choice carries a text label + icon, not just a border).
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FeedbackView } from "./FeedbackView";
import { toFeedbackVM } from "@/lib/translators/feedback_vm";
import type { Answer, Question, Verdict } from "@/lib/wire/engine_entities";

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
      A: "A is correct: singular collective noun.",
      B: "B tempted you: sounds plural.",
    },
    why_correct_md: "…",
    why_tempted_md: "…",
    rule_md: "Collective nouns are singular.",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

function render(verdict: Verdict, answer: Answer): Document {
  const vm = toFeedbackVM(question(), verdict, answer);
  const html = renderToStaticMarkup(React.createElement(FeedbackView, { vm }));
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

describe("FeedbackView — wrong pick (edge first, FR-E3/E4)", () => {
  const doc = render(
    { correct: false, correct_letter: "A", rationale_key: "B" },
    { letter: "B" },
  );

  it("shows the soft banner, not celebrate", () => {
    const banner = doc.querySelector('[data-testid="feedback-banner"]');
    expect(banner?.getAttribute("data-banner")).toBe("soft");
  });

  it("styles the correct row 'correct' and the chosen-wrong row 'chosen-wrong' (FR-E4)", () => {
    expect(doc.querySelector('[data-testid="choice-A"]')?.getAttribute("data-state")).toBe("correct");
    expect(doc.querySelector('[data-testid="choice-B"]')?.getAttribute("data-state")).toBe("chosen-wrong");
    expect(doc.querySelector('[data-testid="choice-C"]')?.getAttribute("data-state")).toBe("other");
  });

  it("never conveys state by color alone — each state row carries a text label (FR-A8)", () => {
    expect(doc.querySelector('[data-testid="choice-A"]')?.textContent).toContain("CORRECT ANSWER");
    expect(doc.querySelector('[data-testid="choice-B"]')?.textContent).toContain("YOUR CHOICE");
  });

  it("renders the distractor rationale and the rule under test (FR-E1)", () => {
    const body = doc.body.textContent ?? "";
    expect(body).toContain("B tempted you");
    expect(body).toContain("Collective nouns are singular.");
  });
});

describe("FeedbackView — correct pick (FR-E2)", () => {
  it("shows the celebrate banner", () => {
    const doc = render(
      { correct: true, correct_letter: "A", rationale_key: "A" },
      { letter: "A" },
    );
    expect(doc.querySelector('[data-testid="feedback-banner"]')?.getAttribute("data-banner")).toBe("celebrate");
  });
});

describe("FeedbackView — green-span recap (BP-2c / FR-7)", () => {
  it("renders feedback-recap with underlined span from context_html", () => {
    const doc = render(
      { correct: true, correct_letter: "A", rationale_key: "A" },
      { letter: "A" },
    );
    const recap = doc.querySelector('[data-testid="feedback-recap"]');
    expect(recap).not.toBeNull();
    expect(recap?.getAttribute("data-has-underline")).toBe("true");
    expect(recap?.querySelector("u")?.textContent).toBe("have");
  });

  it("renders plain recap without inventing u when context has none", () => {
    const vm = toFeedbackVM(
      question({
        context_html: "Plain sentence with no underline.",
        stem: "Which is best?",
      }),
      { correct: true, correct_letter: "A", rationale_key: "A" },
      { letter: "A" },
    );
    const html = renderToStaticMarkup(
      React.createElement(FeedbackView, { vm }),
    );
    const doc = new JSDOM(`<!doctype html><html><body>${html}</body></html>`)
      .window.document;
    const recap = doc.querySelector('[data-testid="feedback-recap"]');
    expect(recap?.getAttribute("data-has-underline")).toBe("false");
    expect(recap?.querySelector("u")).toBeNull();
    expect(recap?.textContent).toContain("Which is best?");
  });
});

describe("FeedbackView — Ask the coach (BP-2d / FR-5)", () => {
  it("omits ask-coach control when onAskCoach is absent", () => {
    const doc = render(
      { correct: true, correct_letter: "A", rationale_key: "A" },
      { letter: "A" },
    );
    expect(doc.querySelector('[data-testid="feedback-ask-coach"]')).toBeNull();
  });

  it("renders ask-coach when onAskCoach is provided", () => {
    const vm = toFeedbackVM(
      question(),
      { correct: true, correct_letter: "A", rationale_key: "A" },
      { letter: "A" },
    );
    const html = renderToStaticMarkup(
      React.createElement(FeedbackView, { vm, onAskCoach: () => {} }),
    );
    const doc = new JSDOM(`<!doctype html><html><body>${html}</body></html>`)
      .window.document;
    expect(doc.querySelector('[data-testid="feedback-ask-coach"]')?.textContent)
      .toContain("Ask the coach");
  });
});

describe("FeedbackView — FBK-2 self-explanation input", () => {
  it("renders an optional self-explanation textarea with the affordance copy", () => {
    const doc = render(
      { correct: false, correct_letter: "A", rationale_key: "B" },
      { letter: "B" },
    );
    const textarea = doc.querySelector<HTMLTextAreaElement>(
      '[data-testid="feedback-self-explanation"]',
    );
    expect(textarea).not.toBeNull();
    // Placeholder carries the "Saying it back makes it stick" affordance.
    expect(textarea?.getAttribute("placeholder")).toMatch(/back/i);
  });

  it("never gates progression — the textarea is not required", () => {
    const doc = render(
      { correct: true, correct_letter: "A", rationale_key: "A" },
      { letter: "A" },
    );
    const textarea = doc.querySelector<HTMLTextAreaElement>(
      '[data-testid="feedback-self-explanation"]',
    );
    expect(textarea?.hasAttribute("required")).toBe(false);
  });

  it("appears on the walked-through resolution too (parity across outcomes)", () => {
    const vm = toFeedbackVM(
      question(),
      { correct: false, correct_letter: "A", rationale_key: "B" },
      { letter: "B" },
      "walked_through",
    );
    const html = renderToStaticMarkup(
      React.createElement(FeedbackView, { vm }),
    );
    const doc = new JSDOM(`<!doctype html><html><body>${html}</body></html>`)
      .window.document;
    expect(
      doc.querySelector('[data-testid="feedback-self-explanation"]'),
    ).not.toBeNull();
  });
});

describe("FeedbackView — G5 why-tempted wrapper (FBK-1)", () => {
  it("wraps the why-tempted block in a feedback-why-tempted element", () => {
    const doc = render(
      { correct: false, correct_letter: "A", rationale_key: "B" },
      { letter: "B" },
    );
    const whyTempted = doc.querySelector(
      '[data-testid="feedback-why-tempted"]',
    );
    expect(whyTempted).not.toBeNull();
    expect(whyTempted?.textContent).toContain("Why B tempted you");
  });

  it("omits the why-tempted block on a correct pick (no distractor to explain)", () => {
    const doc = render(
      { correct: true, correct_letter: "A", rationale_key: "A" },
      { letter: "A" },
    );
    expect(
      doc.querySelector('[data-testid="feedback-why-tempted"]'),
    ).toBeNull();
  });
});
