/**
 * Phase 1.6 — SummaryView SSR structural tests (FR-G1/G2/A8, L1 jsdom).
 *
 * Repo convention (no @testing-library/react): renderToStaticMarkup + JSDOM.
 * The gather/delta logic is proven in use_summary.test.ts; here we assert the
 * view renders a SummaryVM faithfully. Edge/a11y first: an UNKNOWN mastery delta
 * (absent session-start snapshot, ADR-0011 §4) renders "—", not "+0%".
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { SummaryView } from "./SummaryView";
import type { SummaryVM } from "./use_summary";
import type { SessionSummaryVM } from "@/lib/translators/session_summary_vm";

function summary(over: Partial<SessionSummaryVM> = {}): SessionSummaryVM {
  return {
    scoreCorrect: 7,
    scoreTotal: 10,
    scoreTile: "7/10",
    masteryDeltaTile: "+8%",
    timeTile: "12 min",
    recommended: {
      skillId: "s-conc",
      skillName: "Conciseness",
      mode: "drill",
      accentVar: "--color-bucket-conciseness",
    },
    ...over,
  };
}

function vm(over: Partial<SummaryVM> = {}): SummaryVM {
  return { summary: summary(), masteryDeltaKnown: true, ...over };
}

function dom(node: React.ReactElement): Document {
  return new JSDOM(renderToStaticMarkup(node)).window.document;
}

describe("SummaryView — FR-G1 delta unknown renders em-dash (edge first, ADR §4)", () => {
  it('an unknown mastery delta shows "—", never the fabricated "+0%"', () => {
    const doc = dom(<SummaryView vm={vm({ masteryDeltaKnown: false })} />);
    const tile = doc.querySelector('[data-testid="summary-delta"]');
    expect(tile, "delta tile must render").not.toBeNull();
    expect(tile!.textContent).toContain("—");
    expect(tile!.textContent).not.toContain("%");
  });

  it("a known delta shows the signed percent", () => {
    const doc = dom(<SummaryView vm={vm({ masteryDeltaKnown: true })} />);
    const tile = doc.querySelector('[data-testid="summary-delta"]')!;
    expect(tile.textContent).toContain("+8%");
  });
});

describe("SummaryView — FR-G1 stat tiles (stored values)", () => {
  it("renders the stored score and time tiles", () => {
    const doc = dom(<SummaryView vm={vm()} />);
    expect(doc.querySelector('[data-testid="summary-score"]')!.textContent).toContain("7/10");
    expect(doc.querySelector('[data-testid="summary-time"]')!.textContent).toContain("12 min");
  });
});

describe("SummaryView — FR-G2 recommended-next re-opens Quiz", () => {
  it("names the skill and links its CTA to the Quiz route", () => {
    const doc = dom(<SummaryView vm={vm()} />);
    const rec = doc.querySelector('[data-testid="summary-recommended"]');
    expect(rec, "recommended card must render").not.toBeNull();
    expect(rec!.textContent).toContain("Conciseness");
    const cta = doc.querySelector('[data-testid="summary-start-next"]');
    expect(cta?.getAttribute("href")).toContain("/quiz");
  });
});
