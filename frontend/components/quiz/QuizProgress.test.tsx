/**
 * S4 — QuizProgress SSR structural tests (FR-1/FR-2/FR-5/FR-7, L1 jsdom).
 *
 * Repo convention: renderToStaticMarkup + JSDOM (no RTL), twin of QuizView.test.tsx.
 * The component is presentational (F-R1) — it renders a QuizProgressVM, so every
 * case is a fixed VM in, DOM assertion out; the counting math is the translator's
 * job and is tested in quiz_progress_vm.test.ts.
 *
 * Failure/edge first: endless (total null → no "of M"), over-run (bar full but
 * counter drops "of"), then the a11y progressbar semantics and the fill width.
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QuizProgress } from "./QuizProgress";
import type { QuizProgressVM } from "@/lib/translators/quiz_progress_vm";

function render(vm: QuizProgressVM): Document {
  const html = renderToStaticMarkup(
    React.createElement(QuizProgress, { vm }),
  );
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

describe("QuizProgress — endless / over-run (edge first)", () => {
  it("FR-1 endless (total null): shows position, no ' of ' denominator", () => {
    const doc = render({ position: 7, total: null, bounded: false, fraction: 0, complete: false });
    const el = doc.querySelector('[data-testid="quiz-progress"]');
    expect(el).not.toBeNull();
    expect(el?.textContent).toContain("Question 7");
    expect(el?.textContent).not.toContain(" of ");
  });

  it("FR-2 over-run: true position, denominator dropped, bar clamped full", () => {
    const doc = render({ position: 32, total: null, bounded: true, fraction: 1, complete: true });
    const el = doc.querySelector('[data-testid="quiz-progress"]');
    expect(el?.textContent).toContain("Question 32");
    expect(el?.textContent).not.toContain(" of ");
    const fill = doc.querySelector('[data-testid="quiz-progress-fill"]') as HTMLElement | null;
    expect(fill?.style.width).toBe("100%");
  });

  it("FR-7 indeterminate (total null): progressbar OMITS aria-valuenow/valuemax", () => {
    // WAI-ARIA: an indeterminate progressbar (endless OR over-run — both carry
    // total null) must not announce a measured value; omitting the attrs is how AT
    // reports "indeterminate" instead of a misleading "0%"/"100%".
    for (const vm of [
      { position: 7, total: null, bounded: false, fraction: 0, complete: false }, // endless
      { position: 32, total: null, bounded: true, fraction: 1, complete: true }, // over-run
    ] as const) {
      const bar = render(vm).querySelector('[role="progressbar"]');
      expect(bar).not.toBeNull();
      expect(bar?.hasAttribute("aria-valuenow")).toBe(false);
      expect(bar?.hasAttribute("aria-valuemax")).toBe(false);
      // valuemin stays (a stable floor is fine); the text alternative still labels it.
      expect(bar?.getAttribute("aria-valuetext")).toContain(`Question ${vm.position}`);
    }
  });
});

describe("QuizProgress — bounded a11y + fill", () => {
  it("FR-7 exposes a progressbar with aria-valuenow/min/max", () => {
    const doc = render({ position: 15, total: 30, bounded: true, fraction: 0.5, complete: false });
    const bar = doc.querySelector('[role="progressbar"]');
    expect(bar).not.toBeNull();
    expect(bar?.getAttribute("aria-valuemin")).toBe("0");
    expect(bar?.getAttribute("aria-valuemax")).toBe("30");
    expect(bar?.getAttribute("aria-valuenow")).toBe("15");
  });

  it("FR-5 bar fill width matches the fraction", () => {
    const doc = render({ position: 15, total: 30, bounded: true, fraction: 0.5, complete: false });
    const fill = doc.querySelector('[data-testid="quiz-progress-fill"]') as HTMLElement | null;
    expect(fill?.style.width).toBe("50%");
  });

  it("bounded counter shows 'Question N of M'", () => {
    const doc = render({ position: 3, total: 30, bounded: true, fraction: 0.1, complete: false });
    expect(
      doc.querySelector('[data-testid="quiz-progress"]')?.textContent,
    ).toContain("Question 3 of 30");
  });
});
