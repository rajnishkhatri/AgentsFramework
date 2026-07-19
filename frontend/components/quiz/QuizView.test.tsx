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

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { QuizView } from "./QuizView";
import { toQuizItemVM, type QuizItemVM } from "@/lib/translators/quiz_item_vm";
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
    misconception: null,
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

const skillsById = new Map([
  [
    "s-punc",
    { name: "Punctuation", accent_var: "--color-bucket-punctuation" },
  ],
]);

function baseVm(over: Partial<QuizItemVM> = {}): QuizItemVM {
  return { ...toQuizItemVM(question(), skillsById), ...over };
}

function render(props: {
  selectedLetter?: string | null;
  hintOpen?: boolean;
  hint?: string;
  vm?: QuizItemVM;
  endSessionEnabled?: boolean;
  onEndSession?: () => void;
  startedAtIso?: string | null;
}): Document {
  const vm = props.vm ?? toQuizItemVM(question());
  const html = renderToStaticMarkup(
    React.createElement(QuizView, {
      vm,
      selectedLetter: props.selectedLetter ?? null,
      onSelect: () => {},
      onSubmit: () => {},
      hintOpen: props.hintOpen ?? false,
      hint: props.hint ?? "What does 'committee' act as here — one body or many?",
      onToggleHint: () => {},
      ...(props.endSessionEnabled !== undefined
        ? { endSessionEnabled: props.endSessionEnabled }
        : {}),
      ...(props.onEndSession !== undefined
        ? { onEndSession: props.onEndSession }
        : {}),
      ...(props.startedAtIso !== undefined
        ? { startedAtIso: props.startedAtIso }
        : {}),
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

  it("exposes the served skill via data-skill (S3.1 rotation e2e hook)", () => {
    // The skill isn't rendered as visible UI (that's S4), but a stable data-skill
    // on the item root lets the rotation Playwright spec read the served skill
    // deterministically instead of guessing from prose (ADR-0024).
    expect(doc.querySelector('[data-skill="s-punc"]')).not.toBeNull();
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

/**
 * UI FR-D6 / FR-D6a — Reveal is a gated submit alias (Sprint A1).
 * SSR asserts the gate attributes; createRoot asserts the click → onSubmit path
 * (repo has no @testing-library/react).
 */
describe("QuizView — Reveal answer (UI FR-D6 / FR-D6a)", () => {
  it("keeps Reveal non-actionable while nothing is selected (FR-1)", () => {
    const doc = render({ selectedLetter: null });
    const reveal = doc.querySelector('[data-testid="quiz-reveal"]');
    expect(reveal?.hasAttribute("disabled")).toBe(true);
    expect(reveal?.getAttribute("data-enabled")).toBe("false");
  });

  it("renders Reveal as a distinct ghost control (FR-4)", () => {
    const doc = render({ selectedLetter: null });
    const reveal = doc.querySelector('[data-testid="quiz-reveal"]');
    expect(reveal).not.toBeNull();
    expect(reveal?.textContent).toContain("Reveal answer");
    expect(reveal?.className).toMatch(/text-muted/);
  });

  it("uses foreground text when Reveal is enabled (FR-8 polish)", () => {
    const doc = render({ selectedLetter: "A" });
    const reveal = doc.querySelector('[data-testid="quiz-reveal"]');
    expect(reveal?.getAttribute("data-enabled")).toBe("true");
    // Style via data-* (STYLE_GUIDE §13), not a className ternary.
    expect(reveal?.className).toMatch(/data-\[enabled=true\]:text-fg/);
    expect(reveal?.className).toMatch(/text-muted/);
  });

  describe("click → onSubmit (client)", () => {
    let container: HTMLDivElement;
    let root: Root;
    const flush = (): Promise<void> => new Promise((r) => setTimeout(r, 0));

    beforeEach(() => {
      container = document.createElement("div");
      document.body.appendChild(container);
      root = createRoot(container);
    });

    afterEach(() => {
      root.unmount();
      container.remove();
    });

    async function mount(selectedLetter: string | null, onSubmit: () => void) {
      const vm = toQuizItemVM(question());
      root.render(
        React.createElement(QuizView, {
          vm,
          selectedLetter,
          onSelect: () => {},
          onSubmit,
          hintOpen: false,
          hint: "What does 'committee' act as here — one body or many?",
          onToggleHint: () => {},
        }),
      );
      await flush();
    }

    function clickReveal(): void {
      const el = container.querySelector(
        '[data-testid="quiz-reveal"]',
      ) as HTMLElement | null;
      el?.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true }),
      );
    }

    it("does not call onSubmit when Reveal is clicked with no selection (FR-1)", async () => {
      const onSubmit = vi.fn();
      await mount(null, onSubmit);
      clickReveal();
      expect(onSubmit).not.toHaveBeenCalled();
    });

    it("calls onSubmit once when Reveal is clicked with a selection (FR-3)", async () => {
      const onSubmit = vi.fn();
      await mount("B", onSubmit);
      const reveal = container.querySelector('[data-testid="quiz-reveal"]');
      expect(reveal?.hasAttribute("disabled")).toBe(false);
      expect(reveal?.getAttribute("data-enabled")).toBe("true");
      clickReveal();
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });
  });
});

describe("QuizView — D1 skill chip (Q-7)", () => {
  it("renders quiz-skill-chip with skill name and accent dot (FR-Q7-2)", () => {
    const doc = render({
      vm: baseVm(),
      onEndSession: () => {},
      endSessionEnabled: true,
    });
    const chip = doc.querySelector('[data-testid="quiz-skill-chip"]');
    expect(chip).not.toBeNull();
    expect(chip?.textContent).toContain("Punctuation");
    const dot = chip?.querySelector('[data-testid="bucket-dot"]') as
      | HTMLElement
      | null
      | undefined;
    expect(dot).not.toBeNull();
    expect(dot?.style.backgroundColor).toContain(
      "var(--color-bucket-punctuation)",
    );
  });

  it("renders NO chip when skillName is null (FR-Q7-1)", () => {
    const doc = render({
      vm: baseVm({ skillName: null, accentVar: null }),
      onEndSession: () => {},
      endSessionEnabled: true,
    });
    expect(doc.querySelector('[data-testid="quiz-skill-chip"]')).toBeNull();
  });

  it("chip is present whenever the VM carries a skillName (FR-Q7-4)", () => {
    // Same VM in answering and reviewing — the page wraps both phases with the
    // same frame chrome; the leaf just renders the VM fields blindly.
    const doc = render({
      vm: baseVm(),
      onEndSession: () => {},
      endSessionEnabled: true,
    });
    expect(doc.querySelector('[data-testid="quiz-skill-chip"]')?.textContent).toContain(
      "Punctuation",
    );
  });
});

describe("QuizView — D1 End session (Q-8)", () => {
  it("renders quiz-end-session when enabled (FR-Q8-3)", () => {
    const doc = render({
      vm: baseVm(),
      endSessionEnabled: true,
      onEndSession: () => {},
    });
    const btn = doc.querySelector('[data-testid="quiz-end-session"]');
    expect(btn).not.toBeNull();
    expect(btn?.textContent).toContain("End session");
    expect(btn?.hasAttribute("disabled")).toBe(false);
  });

  it("disables End session when endSessionEnabled is false (FR-Q8-1)", () => {
    const doc = render({
      vm: baseVm(),
      endSessionEnabled: false,
      onEndSession: () => {},
    });
    const btn = doc.querySelector('[data-testid="quiz-end-session"]');
    expect(btn?.hasAttribute("disabled")).toBe(true);
  });

  describe("click → onEndSession (client)", () => {
    let container: HTMLDivElement;
    let root: Root;
    const flush = (): Promise<void> => new Promise((r) => setTimeout(r, 0));

    beforeEach(() => {
      container = document.createElement("div");
      document.body.appendChild(container);
      root = createRoot(container);
    });

    afterEach(() => {
      root.unmount();
      container.remove();
    });

    it("fires onEndSession when enabled (FR-Q8-4)", async () => {
      const onEndSession = vi.fn();
      root.render(
        React.createElement(QuizView, {
          vm: baseVm(),
          selectedLetter: null,
          onSelect: () => {},
          onSubmit: () => {},
          hintOpen: false,
          hint: "…",
          onToggleHint: () => {},
          endSessionEnabled: true,
          onEndSession,
        }),
      );
      await flush();
      const btn = container.querySelector(
        '[data-testid="quiz-end-session"]',
      ) as HTMLElement;
      btn.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
      expect(onEndSession).toHaveBeenCalledTimes(1);
    });

    it("does not fire when disabled (FR-Q8-1)", async () => {
      const onEndSession = vi.fn();
      root.render(
        React.createElement(QuizView, {
          vm: baseVm(),
          selectedLetter: null,
          onSelect: () => {},
          onSubmit: () => {},
          hintOpen: false,
          hint: "…",
          onToggleHint: () => {},
          endSessionEnabled: false,
          onEndSession,
        }),
      );
      await flush();
      const btn = container.querySelector(
        '[data-testid="quiz-end-session"]',
      ) as HTMLButtonElement;
      expect(btn.disabled).toBe(true);
      btn.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
      expect(onEndSession).not.toHaveBeenCalled();
    });
  });
});

describe("QuizView — D1 collapsible timer (Q-9)", () => {
  const STARTED = "2026-07-10T10:00:00.000Z";

  it("timer reveal absent when startedAtIso is null (FR-Q9-1)", () => {
    const doc = render({
      vm: baseVm(),
      onEndSession: () => {},
      endSessionEnabled: true,
      startedAtIso: null,
    });
    expect(doc.querySelector('[data-testid="quiz-timer-reveal"]')).toBeNull();
    expect(doc.querySelector('[data-testid="quiz-timer"]')).toBeNull();
  });

  it("default is collapsed — reveal present, clock absent (FR-Q9-2)", () => {
    const doc = render({
      vm: baseVm(),
      onEndSession: () => {},
      endSessionEnabled: true,
      startedAtIso: STARTED,
    });
    expect(doc.querySelector('[data-testid="quiz-timer-reveal"]')).not.toBeNull();
    expect(doc.querySelector('[data-testid="quiz-timer"]')).toBeNull();
  });

  it("reveal is a button with accessible label (FR-Q9-8)", () => {
    const doc = render({
      vm: baseVm(),
      onEndSession: () => {},
      endSessionEnabled: true,
      startedAtIso: STARTED,
    });
    const btn = doc.querySelector('[data-testid="quiz-timer-reveal"]');
    expect(btn?.tagName.toLowerCase()).toBe("button");
    expect(btn?.getAttribute("aria-label")).toBe("Show timer");
  });

  describe("reveal / collapse (client)", () => {
    let container: HTMLDivElement;
    let root: Root;
    const flush = (): Promise<void> => new Promise((r) => setTimeout(r, 0));

    beforeEach(() => {
      container = document.createElement("div");
      document.body.appendChild(container);
      root = createRoot(container);
    });

    afterEach(() => {
      root.unmount();
      container.remove();
    });

    async function mount(startedAtIso: string, key?: string) {
      root.render(
        React.createElement(QuizView, {
          key: key ?? "quiz",
          vm: baseVm(),
          selectedLetter: null,
          onSelect: () => {},
          onSubmit: () => {},
          hintOpen: false,
          hint: "…",
          onToggleHint: () => {},
          endSessionEnabled: true,
          onEndSession: () => {},
          startedAtIso,
        }),
      );
      await flush();
    }

    it("click reveal → quiz-timer renders (FR-Q9-3)", async () => {
      await mount(STARTED);
      const reveal = container.querySelector(
        '[data-testid="quiz-timer-reveal"]',
      ) as HTMLElement;
      reveal.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true }),
      );
      await flush();
      expect(container.querySelector('[data-testid="quiz-timer"]')).not.toBeNull();
      expect(
        container.querySelector('[data-testid="quiz-timer"]')?.textContent,
      ).toMatch(/^\d+:\d{2}$/);
    });

    it("click Hide → quiz-timer removed (FR-Q9-5)", async () => {
      await mount(STARTED);
      const reveal = container.querySelector(
        '[data-testid="quiz-timer-reveal"]',
      ) as HTMLElement;
      reveal.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true }),
      );
      await flush();
      const hide = container.querySelector(
        'button[aria-label="Hide timer"]',
      ) as HTMLElement;
      hide.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true }),
      );
      await flush();
      expect(container.querySelector('[data-testid="quiz-timer"]')).toBeNull();
      expect(
        container.querySelector('[data-testid="quiz-timer-reveal"]'),
      ).not.toBeNull();
    });

    it("remount with new key resets reveal to collapsed (FR-Q9-7)", async () => {
      await mount(STARTED, "q1");
      const reveal = container.querySelector(
        '[data-testid="quiz-timer-reveal"]',
      ) as HTMLElement;
      reveal.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true }),
      );
      await flush();
      expect(container.querySelector('[data-testid="quiz-timer"]')).not.toBeNull();

      await mount(STARTED, "q2");
      expect(container.querySelector('[data-testid="quiz-timer"]')).toBeNull();
      expect(
        container.querySelector('[data-testid="quiz-timer-reveal"]'),
      ).not.toBeNull();
    });
  });
});

describe("QuizView — commit-first coached section (FR-1/2/4/5)", () => {
  it("flag ON pre-submit: no hint toggle, reveal, or ladder (FR-1/2)", () => {
    const html = renderToStaticMarkup(
      React.createElement(QuizView, {
        vm: baseVm(),
        selectedLetter: null,
        onSelect: () => {},
        onSubmit: () => {},
        hintOpen: false,
        hint: "should not show",
        onToggleHint: () => {},
        commitFirstCoach: true,
        coachedLoop: null,
      }),
    );
    const doc = new JSDOM(`<!doctype html><html><body>${html}</body></html>`)
      .window.document;
    expect(doc.querySelector('[data-testid="quiz-hint-toggle"]')).toBeNull();
    expect(doc.querySelector('[data-testid="quiz-reveal"]')).toBeNull();
    expect(doc.querySelector('[data-testid="quiz-coached-section"]')).toBeNull();
  });

  it("flag ON coached loop: n of 3 + nudge; escape only when exhausted (FR-4/5)", () => {
    const loop = {
      wrongLetters: ["A"],
      activeLetter: "A",
      rungsRevealed: { A: 1 },
      exhausted: false,
      rungCap: 3,
    };
    const html = renderToStaticMarkup(
      React.createElement(QuizView, {
        vm: baseVm(),
        selectedLetter: "A",
        onSelect: () => {},
        onSubmit: () => {},
        hintOpen: false,
        hint: "",
        onToggleHint: () => {},
        commitFirstCoach: true,
        coachedLoop: loop,
        renderCoachedInline: true,
        hintLadder: [
          { rung: 1, body_md: "Pump: why A?" },
          { rung: 2, body_md: "Hint: re-read" },
          { rung: 3, body_md: "Prompt: try B" },
        ],
        onNudge: () => {},
        onTryAgain: () => {},
        onEscape: () => {},
      }),
    );
    const doc = new JSDOM(`<!doctype html><html><body>${html}</body></html>`)
      .window.document;
    expect(doc.querySelector('[data-testid="quiz-rung-counter"]')?.textContent).toBe(
      "1 of 3",
    );
    const section = doc.querySelector('[data-testid="quiz-coached-section"]');
    expect(section?.getAttribute("role")).toBe("region");
    expect(section?.getAttribute("aria-label")).toBe("Coaching");
    expect(section?.querySelector("[aria-live='polite']")).not.toBeNull();
    expect(doc.querySelector('[data-testid="quiz-nudge"]')).not.toBeNull();
    expect(doc.querySelector('[data-testid="quiz-escape"]')).toBeNull();

    const exhaustedHtml = renderToStaticMarkup(
      React.createElement(QuizView, {
        vm: baseVm(),
        selectedLetter: "A",
        onSelect: () => {},
        onSubmit: () => {},
        hintOpen: false,
        hint: "",
        onToggleHint: () => {},
        commitFirstCoach: true,
        renderCoachedInline: true,
        coachedLoop: {
          ...loop,
          rungsRevealed: { A: 3 },
          exhausted: true,
        },
        hintLadder: [
          { rung: 1, body_md: "Pump: why A?" },
          { rung: 2, body_md: "Hint: re-read" },
          { rung: 3, body_md: "Prompt: try B" },
        ],
        onNudge: () => {},
        onTryAgain: () => {},
        onEscape: () => {},
      }),
    );
    const exhaustedDoc = new JSDOM(
      `<!doctype html><html><body>${exhaustedHtml}</body></html>`,
    ).window.document;
    expect(exhaustedDoc.querySelector('[data-testid="quiz-try-again"]')).not.toBeNull();
    const escape = exhaustedDoc.querySelector('[data-testid="quiz-escape"]');
    expect(escape).not.toBeNull();
    expect(escape?.getAttribute("aria-describedby")).toBe("quiz-escape-cost");
    expect(exhaustedDoc.querySelector('[data-testid="quiz-escape-cost"]')?.textContent).toContain(
      "won't count as solved",
    );
  });
});
