/**
 * HintLadderList — FR-5/14 structural tests (jsdom + renderToStaticMarkup).
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { HintLadderList, NUDGE_EXHAUSTED_REASON } from "./HintLadderList";
import type { Hint } from "@/lib/wire/engine_entities";

function hint(rung: 1 | 2 | 3, body: string): Hint {
  return {
    id: `h-${rung}`,
    subject: "act-english",
    question_id: "q1",
    choice_letter: null, // item-level ladder (ADR-0035)
    rung,
    body_md: body,
    reviewed: true,
    generated_by: "authored",
  };
}

function dom(node: React.ReactElement): Document {
  return new JSDOM(renderToStaticMarkup(node)).window.document;
}

describe("HintLadderList", () => {
  it("renders revealed rows with expandable chrome + counter", () => {
    const doc = dom(
      <HintLadderList
        revealed={[
          hint(2, "Droppable clauses need fencing. Mark the boundaries."),
          hint(3, "Find where the clause ends. Check the commas."),
        ]}
        totalDeeper={2}
      />,
    );
    expect(doc.querySelector("[data-testid='hint-ladder-list']")).not.toBeNull();
    expect(doc.body?.textContent?.replace(/\s+/g, " ")).toContain("2 of 2 used");
    expect(doc.querySelector("[data-testid='panel-nudge-2']")).not.toBeNull();
    expect(doc.querySelector("[data-testid='panel-nudge-3']")).not.toBeNull();
    expect(
      doc
        .querySelector("[data-testid='panel-nudge-2']")
        ?.getAttribute("aria-expanded"),
    ).not.toBeNull();
  });

  it("exports exhausted reason string for Zone C nudge (FR-5)", () => {
    expect(NUDGE_EXHAUSTED_REASON).toBe(
      "You've used all available nudges for this item",
    );
  });

  it("includes polite announce region (not conversation log)", () => {
    const doc = dom(
      <HintLadderList
        revealed={[hint(2, "A short prompt here.")]}
        totalDeeper={2}
      />,
    );
    const live = doc.querySelector("[aria-live='polite']");
    expect(live).not.toBeNull();
    expect(live?.closest("[role='log']")).toBeNull();
  });

  it("expanded body omits the header prompt (no duplicate first sentence)", () => {
    const doc = dom(
      <HintLadderList
        revealed={[
          hint(
            2,
            "Look closely at the items in the series and consider how they are connected. Pay attention to the punctuation that separates them.",
          ),
        ]}
        totalDeeper={2}
      />,
    );
    const btn = doc.querySelector("[data-testid='panel-nudge-2']");
    expect(btn?.textContent).toContain(
      "Look closely at the items in the series and consider how they are connected.",
    );
    const body = doc.querySelector("#ladder-body-h-2");
    expect(body).not.toBeNull();
    expect(body?.textContent).toContain(
      "Pay attention to the punctuation that separates them.",
    );
    expect(body?.textContent).not.toContain(
      "Look closely at the items in the series and consider how they are connected.",
    );
    // Body shares the rounded card with the header (not a floating white box).
    expect(body?.parentElement?.contains(btn)).toBe(true);
    expect(body?.parentElement?.className).toMatch(/rounded-md/);
  });

  it("single-sentence nudge: no white body (header is the only copy)", () => {
    const doc = dom(
      <HintLadderList
        revealed={[
          hint(2, "In general, how do we punctuate items in a series?"),
        ]}
        totalDeeper={2}
      />,
    );
    expect(doc.querySelector("[data-testid='panel-nudge-2']")?.textContent).toContain(
      "In general, how do we punctuate items in a series?",
    );
    expect(doc.querySelector("#ladder-body-h-2")).toBeNull();
  });
});
