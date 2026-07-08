/**
 * Phase 1.2 — DashboardView SSR structural tests (FR-C2/C3/C5/A8, L1 jsdom).
 *
 * Repo convention (no @testing-library/react): renderToStaticMarkup + JSDOM.
 * The gather/pick logic is proven in use_dashboard.test.ts; here we assert the
 * view renders a DashboardVM faithfully. Edge/a11y first: the "Due" state must
 * carry a TEXT label (not color alone, FR-A8), and the misses control shows its
 * count with a real destination (FR-C5/B5).
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { DashboardView } from "./DashboardView";
import type { DashboardVM } from "./use_dashboard";
import type { BucketCardVM } from "@/lib/translators/bucket_card_vm";

function card(over: Partial<BucketCardVM> = {}): BucketCardVM {
  return {
    skillId: "s-punc",
    name: "Punctuation",
    masteryPct: 42,
    shareOfTestPct: 20,
    accentVar: "--color-bucket-punctuation",
    due: false,
    ...over,
  };
}

function vm(over: Partial<DashboardVM> = {}): DashboardVM {
  return {
    buckets: [
      card({ skillId: "s-punc", name: "Punctuation", due: true }),
      card({ skillId: "s-gram", name: "Grammar", masteryPct: 90 }),
    ],
    todayFocus: {
      present: true,
      skillId: "s-punc",
      skillName: "Punctuation",
      accentVar: "--color-bucket-punctuation",
      questionId: "q1",
      ctaLabel: "Start adaptive session",
    },
    reviewMissesCount: 3,
    ...over,
  };
}

function dom(node: React.ReactElement): Document {
  return new JSDOM(renderToStaticMarkup(node)).window.document;
}

describe("DashboardView — FR-A8 due state is never color-only", () => {
  it('a due card carries a visible "Due" text label, not just an accent', () => {
    const doc = dom(<DashboardView vm={vm()} />);
    const dueCard = doc.querySelector('[data-testid="bucket-s-punc"]');
    expect(dueCard, "due card must render").not.toBeNull();
    expect(dueCard!.getAttribute("data-due")).toBe("true");
    // A screen-reader/no-color user must still know it's due: text present.
    expect(dueCard!.textContent).toContain("Due");
  });

  it("a not-due card has no Due badge", () => {
    const doc = dom(<DashboardView vm={vm()} />);
    const notDue = doc.querySelector('[data-testid="bucket-s-gram"]');
    expect(notDue!.getAttribute("data-due")).toBe("false");
  });
});

describe("DashboardView — FR-5/FR-2/FR-7 bucket card is a focus link", () => {
  it("makes each bucket card a link to the focused quiz (/learn/quiz?focus=<skillId>)", () => {
    const doc = dom(<DashboardView vm={vm()} />);
    const card = doc.querySelector('[data-testid="bucket-s-punc"]');
    expect(card, "bucket card must render").not.toBeNull();
    // The prototype opens a skill/quiz on a bucket click — the card is an <a>,
    // not an inert <article> (the documented-but-unimplemented FR-C4 behavior).
    expect(card!.tagName.toLowerCase()).toBe("a");
    expect(card!.getAttribute("href")).toBe("/learn/quiz?focus=s-punc");
    // FR-7: the accessible name includes the bucket name.
    expect(card!.textContent).toContain("Punctuation");
  });

  it("keeps the card's testid/due/progressbar while being a link", () => {
    const doc = dom(<DashboardView vm={vm()} />);
    const card = doc.querySelector('[data-testid="bucket-s-punc"]')!;
    expect(card.getAttribute("data-due")).toBe("true"); // due state preserved
    // The bucket-colored progressbar still renders inside the card.
    expect(card.querySelector('[role="progressbar"]')).not.toBeNull();
  });

  it("never links to the coming-soon Skill route (FR-2 no dead end)", () => {
    const doc = dom(<DashboardView vm={vm()} />);
    const card = doc.querySelector('[data-testid="bucket-s-gram"]')!;
    expect(card.getAttribute("href")).toBe("/learn/quiz?focus=s-gram");
    expect(card.getAttribute("href")).not.toContain("/learn/skill");
  });
});

describe("DashboardView — FR-C3 mastery grid", () => {
  it("renders one card per bucket showing name, mastery %, and share %", () => {
    const doc = dom(<DashboardView vm={vm()} />);
    const cards = doc.querySelectorAll("[data-testid^=bucket-]");
    expect(cards).toHaveLength(2);
    const punc = doc.querySelector('[data-testid="bucket-s-punc"]')!;
    expect(punc.textContent).toContain("Punctuation");
    expect(punc.textContent).toContain("42%"); // mastery
    expect(punc.textContent).toContain("20%"); // share of test
  });
});

describe("DashboardView — FR-C2 today's-focus banner", () => {
  it("shows the focus skill + a CTA linking to Quiz", () => {
    const doc = dom(<DashboardView vm={vm()} />);
    const banner = doc.querySelector('[data-testid="today-focus"]');
    expect(banner, "focus banner must render").not.toBeNull();
    expect(banner!.textContent).toContain("Punctuation");
    const cta = banner!.querySelector("a");
    expect(cta?.textContent).toContain("Start adaptive session");
    expect(cta?.getAttribute("href")).toContain("/quiz");
  });

  it("hides the banner when there is no focus (cold start)", () => {
    const doc = dom(<DashboardView vm={vm({ todayFocus: { present: false } })} />);
    expect(doc.querySelector('[data-testid="today-focus"]')).toBeNull();
  });
});

describe("DashboardView — FR-C5 review-my-misses", () => {
  it("shows the misses count in the control label", () => {
    const doc = dom(<DashboardView vm={vm({ reviewMissesCount: 3 })} />);
    const misses = doc.querySelector('[data-testid="review-misses"]');
    expect(misses, "misses control must render").not.toBeNull();
    expect(misses!.textContent).toContain("3");
  });
});
