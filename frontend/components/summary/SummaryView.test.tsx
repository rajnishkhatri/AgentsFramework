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

  it('labels the delta tile "Mastery change" (FLAG-6 / FR-7), not absolute "Mastery"', () => {
    const doc = dom(<SummaryView vm={vm()} />);
    const tile = doc.querySelector('[data-testid="summary-delta"]');
    expect(tile!.textContent).toContain("Mastery change");
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

describe("SummaryView — FR-3 CTA uses the brand accent, not the per-bucket accent", () => {
  it("fills the CTA with the bucket-independent brand accent (bg-accent)", () => {
    // The card's <section> rebinds `--accent` to a per-bucket color; palest
    // buckets + white text drop below WCAG-AA (measured ~3.6:1). The CTA must
    // NOT inherit that per-bucket fill — it uses the brand accent utility, whose
    // token (`--color-accent`) is bucket-independent and clears AA (~6.5:1).
    const doc = dom(<SummaryView vm={vm()} />);
    const cta = doc.querySelector('[data-testid="summary-start-next"]')!;
    const cls = cta.getAttribute("class") ?? "";
    expect(cls).toContain("bg-accent");
    // The regression under fix: the CTA must not read the card-scoped --accent.
    expect(cls).not.toContain("bg-[var(--accent)]");
    // On-accent text is retained so the pairing is the AA-verified brand pair.
    expect(cls).toContain("text-on-accent");
  });
});

describe("SummaryView — FR-4/FR-2/FR-7 recommended-skill name is a focus link", () => {
  it("makes the skill name a link to the focused quiz (/learn/quiz?focus=<skillId>)", () => {
    const doc = dom(<SummaryView vm={vm()} />);
    // The skill name must be an <a> (not an inert <p>) — the prototype opens a
    // skill/quiz on a skill click. Match the link by its focus href.
    const link = doc.querySelector('a[data-testid="summary-skill-link"]');
    expect(link, "skill name must be a link").not.toBeNull();
    expect(link!.getAttribute("href")).toBe("/learn/quiz?focus=s-conc");
    // FR-7: the accessible name includes the skill name.
    expect(link!.textContent).toContain("Conciseness");
  });

  it("never links to the coming-soon Skill route (FR-2 no dead end)", () => {
    const doc = dom(<SummaryView vm={vm()} />);
    const link = doc.querySelector('a[data-testid="summary-skill-link"]')!;
    expect(link.getAttribute("href")).not.toContain("/learn/skill");
  });
});

describe("SummaryView — FR-8 non-regression (label, route, stat tiles unchanged)", () => {
  it("keeps the CTA label, its /quiz route, and the three stat tiles intact", () => {
    const doc = dom(<SummaryView vm={vm()} />);
    const cta = doc.querySelector('[data-testid="summary-start-next"]')!;
    expect(cta.textContent).toContain("Practice this next");
    expect(cta.getAttribute("href")).toContain("/quiz");
    // The three stat tiles still render (FR-G1 unchanged).
    expect(doc.querySelector('[data-testid="summary-score"]')).not.toBeNull();
    expect(doc.querySelector('[data-testid="summary-delta"]')).not.toBeNull();
    expect(doc.querySelector('[data-testid="summary-time"]')).not.toBeNull();
  });
});
