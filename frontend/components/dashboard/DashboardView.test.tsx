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
    masteryKnown: true,
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
    greeting: {
      headline: "Good afternoon, Garvit",
      subline: "Friday, July 10",
    },
    rail: {
      status: "ok",
      streak: { present: true, days: 3 },
      weekly: { count: 2, target: 3, label: "2 / 3 sessions" },
    },
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

describe("DashboardView — FR-5/FR-7 bucket card opens Skill detail (SD-6)", () => {
  it("makes each bucket card a link to Skill detail (/learn/skill?skillId=<skillId>)", () => {
    const doc = dom(<DashboardView vm={vm()} />);
    const card = doc.querySelector('[data-testid="bucket-s-punc"]');
    expect(card, "bucket card must render").not.toBeNull();
    // SD-6: the prototype opens Skill detail (the teach plane) on a bucket click.
    // /learn/skill is live now (E1a/ADR-0028), so the card links there — the card
    // is an <a>, not an inert <article> (FR-C4).
    expect(card!.tagName.toLowerCase()).toBe("a");
    expect(card!.getAttribute("href")).toBe("/learn/skill?skillId=s-punc");
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

  it("links to the live Skill route, never the old quiz-drill target (SD-6)", () => {
    const doc = dom(<DashboardView vm={vm()} />);
    const card = doc.querySelector('[data-testid="bucket-s-gram"]')!;
    expect(card.getAttribute("href")).toBe("/learn/skill?skillId=s-gram");
    expect(card.getAttribute("href")).not.toContain("/learn/quiz?focus=");
  });
});

describe("DashboardView — FR-C3 mastery grid", () => {
  it("renders one card per bucket showing name, mastery %, and share %", () => {
    const doc = dom(<DashboardView vm={vm()} />);
    const cards = doc.querySelectorAll("[data-testid^='bucket-s-']");
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

  it("links to a review-mode quiz (?mode=review), not plain adaptive", () => {
    const doc = dom(<DashboardView vm={vm({ reviewMissesCount: 11 })} />);
    const misses = doc.querySelector('[data-testid="review-misses"]');
    expect(misses!.getAttribute("href")).toBe("/learn/quiz?mode=review");
  });
});

describe("DashboardView — C1 rail + greeting (FR-1/FR-5/FR-14)", () => {
  it("rail_classes_include_container_query_variants", () => {
    const markup = renderToStaticMarkup(<DashboardView vm={vm()} />);
    expect(markup).toContain("@container");
    expect(markup).toContain("@lg:");
  });

  it("no_goal_or_note_tile_rendered", () => {
    const doc = dom(<DashboardView vm={vm()} />);
    const text = (doc.body.textContent ?? "").toLowerCase();
    expect(text).not.toMatch(/score\s*goal/);
    expect(text).not.toMatch(/coach\s*note/);
    expect(text).not.toContain("goal tile");
  });

  it("unavailable_state_renders_retry_button", () => {
    const doc = dom(
      <DashboardView
        vm={vm({
          rail: {
            status: "unavailable",
            streak: { present: false, days: 0 },
            weekly: { count: 0, target: 3, label: "—" },
          },
        })}
      />,
    );
    expect(doc.querySelector('[data-testid="rail-retry"]')?.textContent).toBe(
      "Retry",
    );
    expect(doc.body.textContent).toContain("Trust rail unavailable");
    expect(doc.querySelector('[data-testid="streak-tile"]')).toBeNull();
    expect(doc.querySelector('[data-testid="weekly-tile"]')).toBeNull();
    // Header + mastery still present (FR-1).
    expect(doc.querySelector("header")?.textContent).toContain("Good afternoon, Garvit");
    expect(doc.querySelector('[aria-label="Skill mastery"]')).not.toBeNull();
  });

  // FR-7: aria-live landmark identity is stable across ok ↔ unavailable.
  it("aria_live_region_landmark_stable_across_ok_unavailable", () => {
    const okDoc = dom(<DashboardView vm={vm()} />);
    const okLive = okDoc.querySelector('[aria-live="polite"]');
    expect(okLive, "ok state must have aria-live host").not.toBeNull();
    const okTag = okLive!.tagName;
    const okLabel = okLive!.getAttribute("aria-label");

    const badDoc = dom(
      <DashboardView
        vm={vm({
          rail: {
            status: "unavailable",
            streak: { present: false, days: 0 },
            weekly: { count: 0, target: 3, label: "—" },
          },
        })}
      />,
    );
    const badLive = badDoc.querySelector('[aria-live="polite"]');
    expect(badLive, "unavailable state must have aria-live host").not.toBeNull();
    expect(badLive!.tagName).toBe(okTag);
    expect(badLive!.getAttribute("aria-label")).toBe(okLabel);
    // Landmark is the <aside>, not an inner wrapper that swaps.
    expect(badLive!.getAttribute("data-testid")).toBe("trust-rail");
    expect(okLive!.getAttribute("data-testid")).toBe("trust-rail");
  });

  // FR-8: rail status swap must not rewrite greeting or bucket markup.
  it("retry_does_not_rerender_greeting_or_buckets", () => {
    const ok = vm();
    const okDoc = dom(<DashboardView vm={ok} />);
    const greetingSnap = okDoc.querySelector(
      '[data-testid="dashboard-greeting"]',
    )?.outerHTML;
    const bucketSnap = okDoc.querySelector("[data-testid^='bucket-s-']")?.outerHTML;
    expect(greetingSnap).toBeTruthy();
    expect(bucketSnap).toBeTruthy();

    const swapped = dom(
      <DashboardView
        vm={vm({
          rail: {
            status: "unavailable",
            streak: { present: false, days: 0 },
            weekly: { count: 0, target: 3, label: "—" },
          },
        })}
      />,
    );
    expect(
      swapped.querySelector('[data-testid="dashboard-greeting"]')?.outerHTML,
    ).toBe(greetingSnap);
    expect(
      swapped.querySelector("[data-testid^='bucket-s-']")?.outerHTML,
    ).toBe(bucketSnap);
  });
});
