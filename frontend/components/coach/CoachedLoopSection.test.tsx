/**
 * T19 — conversational coached-loop transcript (V1, V6, V10).
 * Red-first: pick echo, ack turn, per-rung turns, stuck echoes, stable nudge label.
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { CoachedLoopSection } from "./CoachedLoopSection";
import type { Question } from "@/lib/wire/engine_entities";

function question(over: Partial<Question> = {}): Question {
  return {
    id: "q1",
    subject: "act-english",
    skill_id: "s-punc",
    difficulty: 2,
    context_html: "…",
    stem: "Which?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "keep", is_no_change: false },
      { letter: "C", label: "are keeping", is_no_change: false },
      { letter: "D", label: "have kept", is_no_change: false },
    ],
    answer_letter: "A",
    per_choice_rationale: {
      A: "subject-verb",
      B: "tempted by nearby plural",
    },
    why_correct_md: "…",
    why_tempted_md: "…",
    rule_md: "…",
    item_type: "underlined-span-mc",
    misconception: "nearby-plural distractor",
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

const LADDER = [
  { rung: 1, body_md: "Pump: which word agrees?" },
  { rung: 2, body_md: "Hint: strip the prep phrase." },
  { rung: 3, body_md: "Prompt: re-test agreement." },
];

/** Turn testids only — excludes quiz-rung-counter (also starts with quiz-rung-). */
function turnOrder(doc: Document): string[] {
  return [
    ...doc.querySelectorAll(
      "[data-testid='quiz-pick-echo'], [data-testid='quiz-coached-ack'], [data-testid='quiz-rung-1'], [data-testid='quiz-rung-2'], [data-testid='quiz-rung-3'], [data-testid^='quiz-stuck-echo']",
    ),
  ].map((el) => el.getAttribute("data-testid")!);
}

function render(over: {
  rungsRevealed?: number;
  exhausted?: boolean;
  letter?: string;
}): Document {
  const letter = over.letter ?? "B";
  const rungs = over.rungsRevealed ?? 1;
  const html = renderToStaticMarkup(
    React.createElement(CoachedLoopSection, {
      coachedLoop: {
        wrongLetters: [letter],
        activeLetter: letter,
        rungsRevealed: { [letter]: rungs },
        exhausted: over.exhausted ?? false,
        rungCap: 3,
      },
      hintLadder: LADDER,
      onNudge: () => {},
      onTryAgain: () => {},
      onEscape: () => {},
      ackQuestion: question(),
    }),
  );
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

describe("CoachedLoopSection — T19 conversational transcript (V1/V6)", () => {
  it("rung 1: pick echo + ack turn + rung turn; nudge stays Show me more", () => {
    const doc = render({ rungsRevealed: 1 });

    const echo = doc.querySelector('[data-testid="quiz-pick-echo"]');
    expect(echo?.textContent).toBe("I chose B.");

    expect(doc.querySelector('[data-testid="quiz-coached-ack"]')).not.toBeNull();
    expect(doc.querySelector('[data-testid="quiz-rung-1"]')?.textContent).toContain(
      "Pump: which word agrees?",
    );

    const transcript = doc.querySelector('[data-testid="quiz-coached-transcript"]');
    expect(transcript?.getAttribute("role")).toBe("log");

    // Turns appear in conversational order: pick → ack → rung1
    const order = turnOrder(doc);
    expect(order).toEqual([
      "quiz-pick-echo",
      "quiz-coached-ack",
      "quiz-rung-1",
    ]);

    expect(doc.querySelector('[data-testid="quiz-nudge"]')?.textContent).toBe(
      "Show me more →",
    );
    expect(doc.querySelector('[data-testid^="quiz-stuck-echo"]')).toBeNull();
  });

  it("rung 2+: inserts learner 'I'm still stuck.' echo before each later rung (V1/V6)", () => {
    const doc = render({ rungsRevealed: 2 });

    const order = turnOrder(doc);
    expect(order).toEqual([
      "quiz-pick-echo",
      "quiz-coached-ack",
      "quiz-rung-1",
      "quiz-stuck-echo-2",
      "quiz-rung-2",
    ]);
    expect(
      doc.querySelector('[data-testid="quiz-stuck-echo-2"]')?.textContent,
    ).toBe("I'm still stuck.");

    // V6: button label never flips to "I'm still stuck →"
    expect(doc.querySelector('[data-testid="quiz-nudge"]')?.textContent).toBe(
      "Show me more →",
    );
  });

  it("at rung cap−1 the nudge label still stays Show me more (V6)", () => {
    const doc = render({ rungsRevealed: 2 });
    expect(doc.querySelector('[data-testid="quiz-nudge"]')?.textContent).toBe(
      "Show me more →",
    );
    expect(doc.body.textContent).not.toMatch(/I'm still stuck →/);
  });
});

describe("CoachedLoopSection — T24 controls (V4/V5/V7)", () => {
  it("offers Let me try again from rung 1 alongside Show me more (V5)", () => {
    const doc = render({ rungsRevealed: 1 });
    expect(doc.querySelector('[data-testid="quiz-try-again"]')).not.toBeNull();
    expect(doc.querySelector('[data-testid="quiz-nudge"]')).not.toBeNull();
    expect(doc.querySelector('[data-testid="quiz-escape"]')).toBeNull();
  });

  it("exhaustion: try-again is primary, escape is secondary (V7)", () => {
    const doc = render({ rungsRevealed: 3, exhausted: true });
    const tryAgain = doc.querySelector('[data-testid="quiz-try-again"]');
    const escape = doc.querySelector('[data-testid="quiz-escape"]');
    expect(tryAgain?.getAttribute("data-priority")).toBe("primary");
    expect(escape?.getAttribute("data-priority")).toBe("secondary");
    // Primary fills; secondary outlines.
    expect(tryAgain?.className).toMatch(/bg-accent/);
    expect(escape?.className).toMatch(/border-accent/);
    expect(escape?.className).not.toMatch(/bg-accent/);
  });
});

describe("CoachedLoopSection — T21 MOM-9 ladder rail (V3)", () => {
  it("shows PUMP→HINT→PROMPT rail with fill matching nudges revealed", () => {
    const doc = render({ rungsRevealed: 2 });
    const rail = doc.querySelector('[data-testid="quiz-ladder-rail"]');
    expect(rail).not.toBeNull();
    expect(rail?.getAttribute("aria-label")).toMatch(/least help first/i);
    expect(rail?.getAttribute("aria-label")).not.toMatch(/\brung\b/i);

    expect(
      doc
        .querySelector('[data-testid="quiz-ladder-stage-pump"]')
        ?.getAttribute("data-filled"),
    ).toBe("true");
    expect(
      doc
        .querySelector('[data-testid="quiz-ladder-stage-hint"]')
        ?.getAttribute("data-filled"),
    ).toBe("true");
    expect(
      doc
        .querySelector('[data-testid="quiz-ladder-stage-prompt"]')
        ?.getAttribute("data-filled"),
    ).toBe("false");
  });

  it("labels each revealed coach nudge with stage badge + no-answer shield", () => {
    const doc = render({ rungsRevealed: 2 });
    expect(
      doc.querySelector('[data-testid="quiz-rung-stage-1"]')?.textContent,
    ).toMatch(/PUMP/i);
    expect(
      doc.querySelector('[data-testid="quiz-rung-stage-1"]')?.textContent,
    ).toMatch(/no answer/i);
    expect(
      doc.querySelector('[data-testid="quiz-rung-stage-2"]')?.textContent,
    ).toMatch(/HINT/i);
    expect(
      doc.querySelector('[data-testid="quiz-rung-stage-2"]')?.textContent,
    ).toMatch(/no answer/i);
  });
});

describe("CoachedLoopSection — Phase-3 residual R1 (fold + bleed)", () => {
  it("exhaustion action footer is opaque (no translucent bleed-through)", () => {
    const doc = render({ rungsRevealed: 3, exhausted: true });
    const actions = doc.querySelector('[data-testid="quiz-exhaustion-actions"]');
    const cls = actions?.getAttribute("class") ?? "";
    expect(cls).not.toContain("bg-surface/95");
    expect(cls).not.toContain("backdrop-blur");
    expect(cls).toContain("bg-surface");
  });

  it("scrolls the actions row into view when a rung is revealed", async () => {
    const { vi } = await import("vitest");
    const spy = vi.fn();
    const proto = window.HTMLElement.prototype as unknown as {
      scrollIntoView?: (o?: unknown) => void;
    };
    const orig = proto.scrollIntoView;
    proto.scrollIntoView = spy;
    const { createRoot } = await import("react-dom/client");
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    const flush = (): Promise<void> => new Promise((r) => setTimeout(r, 0));

    const props = (rungs: number) =>
      React.createElement(CoachedLoopSection, {
        coachedLoop: {
          wrongLetters: ["B"],
          activeLetter: "B",
          rungsRevealed: { B: rungs },
          exhausted: false,
          rungCap: 3,
        },
        hintLadder: LADDER,
        onNudge: () => {},
        onTryAgain: () => {},
        onEscape: () => {},
        ackQuestion: question(),
      });

    root.render(props(1));
    await flush();
    spy.mockClear();
    root.render(props(2));
    await flush();
    expect(spy).toHaveBeenCalled();

    root.unmount();
    container.remove();
    if (orig != null) proto.scrollIntoView = orig;
    else delete proto.scrollIntoView;
  });
});
