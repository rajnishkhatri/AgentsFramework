/**
 * CoachedConfirmSection — the in-place SOLVE confirmation (FR-15 / V30).
 *
 * The confirm serves BOTH correct paths now: first-try and coached. The result
 * label + affirmation turn must switch on `confirm.resolution`, mirroring the v3
 * prototype's `resultLabel` ("Solved on first try" vs "Worked through it with the
 * coach"). Failure-path first: a first-try confirm must NOT read as coached.
 */

import { describe, expect, it } from "vitest";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { JSDOM } from "jsdom";
import { CoachedConfirmSection } from "./CoachedConfirmSection";
import type { CoachedConfirmState } from "@/components/quiz/quiz_screen_reducer";

function render(confirm: CoachedConfirmState): Document {
  const html = renderToStaticMarkup(
    React.createElement(CoachedConfirmSection, {
      confirm,
      onSeeBreakdown: () => {},
    }),
  );
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

const base = {
  correctLetter: "B",
  answeredLetter: "B",
  whySummary: "Singular subject takes the singular verb.",
} as const;

describe("CoachedConfirmSection — result label switches on resolution (V30)", () => {
  it("a coached solve reads 'Worked through it with the coach'", () => {
    const doc = render({ ...base, resolution: "coached" });
    const label = doc.querySelector(
      '[data-testid="quiz-coached-confirm-label"]',
    );
    expect(label?.textContent).toBe("Worked through it with the coach");
  });

  it("a first-try solve reads 'Solved on first try' — NOT the coached label", () => {
    const doc = render({ ...base, resolution: "first_try" });
    const label = doc.querySelector(
      '[data-testid="quiz-coached-confirm-label"]',
    );
    expect(label?.textContent).toBe("Solved on first try");
    expect(label?.textContent).not.toContain("coach");
  });

  it("the affirmation turn does not claim a trap was worked through on a first-try solve", () => {
    const doc = render({ ...base, resolution: "first_try" });
    const turn = doc.querySelector('[data-testid="quiz-coached-confirm-turn"]');
    expect(turn?.textContent ?? "").not.toContain("worked through the trap");
  });

  it("the opt-in breakdown control renders for both resolutions (still opt-in, not forced)", () => {
    for (const resolution of ["first_try", "coached"] as const) {
      const doc = render({ ...base, resolution });
      expect(
        doc.querySelector('[data-testid="quiz-see-breakdown"]'),
      ).not.toBeNull();
    }
  });
});
