/**
 * ProgressView — Epic F FR-1/10/11/12 + DT-3/5/6/7.
 * Repo convention: renderToStaticMarkup + JSDOM.
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ProgressView } from "./ProgressView";
import type { ProgressScreenVM } from "@/lib/translators/progress_screen_vm";
import type { BucketCardVM } from "@/lib/translators/bucket_card_vm";

function bucket(over: Partial<BucketCardVM> = {}): BucketCardVM {
  return {
    skillId: over.skillId ?? "s-punc",
    name: over.name ?? "Punctuation",
    masteryPct: over.masteryPct ?? 42,
    shareOfTestPct: over.shareOfTestPct ?? 15,
    accentVar: over.accentVar ?? "--color-bucket-punctuation",
    due: over.due ?? false,
  };
}

function vm(over: Partial<ProgressScreenVM> = {}): ProgressScreenVM {
  return {
    header: {
      itemsReviewed: over.header?.itemsReviewed ?? 0,
      streak: over.header?.streak ?? { present: false, days: 0 },
    },
    trend: over.trend ?? { points: [], range: "all" },
    buckets: over.buckets ?? [
      bucket({ skillId: "s-rhet", name: "Rhetoric", due: true, masteryPct: 55 }),
      bucket({ skillId: "s-usage", name: "Usage", masteryPct: 40 }),
      bucket({ skillId: "s-punc", name: "Punctuation", masteryPct: 70 }),
      bucket({ skillId: "s-org", name: "Organization", masteryPct: 30 }),
      bucket({ skillId: "s-struct", name: "Sentence Structure", masteryPct: 20 }),
      bucket({ skillId: "s-conc", name: "Conciseness", masteryPct: 10 }),
    ],
  };
}

function dom(node: React.ReactElement): Document {
  return new JSDOM(renderToStaticMarkup(node)).window.document;
}

describe("ProgressView — Epic F", () => {
  it("renders header items-reviewed and streak (FR-10/11)", () => {
    const doc = dom(
      <ProgressView
        vm={vm({
          header: {
            itemsReviewed: 147,
            streak: { present: true, days: 9 },
          },
        })}
        range="all"
        onRangeChange={() => {}}
      />,
    );
    const root = doc.querySelector('[data-testid="progress-root"]');
    expect(root).not.toBeNull();
    expect(root!.textContent).toMatch(/147 items reviewed/);
    expect(root!.textContent).toMatch(/9-day streak/);
  });

  it("shows honest empty state when points empty (FR-1 / DT-5)", () => {
    const doc = dom(
      <ProgressView
        vm={vm({ trend: { points: [], range: "30d" } })}
        range="30d"
        onRangeChange={() => {}}
      />,
    );
    const empty = doc.querySelector('[data-testid="progress-trend-empty"]');
    expect(empty).not.toBeNull();
    expect(empty!.textContent ?? "").toMatch(/Not enough history yet/i);
    expect(doc.querySelector("polyline")).toBeNull();
  });

  it("hides range tabs on narrow container via @container (DT-6)", () => {
    const markup = renderToStaticMarkup(
      <ProgressView vm={vm()} range="all" onRangeChange={() => {}} />,
    );
    expect(markup).toContain("@container");
    // Tabs exist in DOM but are layout-hidden until @md (not a dead control).
    const doc = new JSDOM(markup).window.document;
    const tabs = doc.querySelector('[data-testid="progress-range-tabs"]');
    expect(tabs).not.toBeNull();
    expect(tabs!.className).toMatch(/hidden/);
    expect(tabs!.className).toMatch(/@md:/);
  });

  it("DUE badge + numeric % (DT-3/7 — color never sole signal)", () => {
    const doc = dom(
      <ProgressView vm={vm()} range="all" onRangeChange={() => {}} />,
    );
    const due = doc.querySelector('[data-testid="mastery-due-s-rhet"]');
    expect(due).not.toBeNull();
    expect(due!.textContent?.toUpperCase()).toContain("DUE");
    const pct = doc.querySelector('[data-testid="mastery-pct-s-rhet"]');
    expect(pct).not.toBeNull();
    expect(pct!.textContent).toMatch(/55%/);
  });

  it("trend caption is Accuracy trend, not projected score (FR-3)", () => {
    const doc = dom(
      <ProgressView
        vm={vm({
          trend: {
            points: [
              { atISO: "2026-07-08T10:00:00.000Z", accuracyPct: 40 },
              { atISO: "2026-07-12T10:00:00.000Z", accuracyPct: 80 },
            ],
            range: "all",
          },
        })}
        range="all"
        onRangeChange={() => {}}
      />,
    );
    expect(doc.body.textContent ?? "").toMatch(/Accuracy trend/i);
    expect(doc.body.textContent ?? "").not.toMatch(/projected|goal 28|on track/i);
  });
});
