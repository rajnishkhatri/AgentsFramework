/**
 * D2 FR-2 + FR-5 — BucketCard header dot glyph.
 *
 * Repo convention (no @testing-library/react): renderToStaticMarkup + JSDOM.
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { BucketCard } from "./BucketCard";
import type { BucketCardVM } from "@/lib/translators/bucket_card_vm";

function card(over: Partial<BucketCardVM> = {}): BucketCardVM {
  return {
    skillId: "s-punc",
    name: "Punctuation",
    masteryKnown: true,
    masteryPct: 42,
    shareOfTestPct: 15,
    accentVar: "--color-bucket-punctuation",
    due: false,
    ...over,
  };
}

function dom(node: React.ReactElement): Document {
  return new JSDOM(renderToStaticMarkup(node)).window.document;
}

describe("BucketCard — D2 bucket-dot glyph", () => {
  it("renders_no_dot_when_accent_var_missing (FR-2)", () => {
    // Defensive fixture: accentVar null (view gates on truthiness).
    const doc = dom(
      <BucketCard
        vm={card({ accentVar: null as unknown as string })}
      />,
    );
    expect(doc.querySelector('[data-testid^="bucket-dot-"]')).toBeNull();
  });

  it("renders_dot_with_accent_variable (FR-5)", () => {
    const doc = dom(<BucketCard vm={card()} />);
    const header = doc.querySelector("header");
    expect(header).not.toBeNull();
    const dot = header!.querySelector(
      '[data-testid="bucket-dot-s-punc"]',
    ) as HTMLElement | null;
    expect(dot).not.toBeNull();
    expect(dot!.getAttribute("aria-hidden")).toBe("true");
    expect(dot!.className).toContain("bg-[var(--accent)]");
    // <dl> a11y guard — definition-list structure unchanged.
    expect(doc.querySelector("dl")).not.toBeNull();
    expect(doc.querySelectorAll("dl > div").length).toBe(2);
  });
});

describe("BucketCard — SD-6 opens Skill detail (not a drill)", () => {
  it("the card links to /learn/skill?skillId=<id>, not the quiz drill", () => {
    const doc = dom(<BucketCard vm={card({ skillId: "s-punc" })} />);
    const link = doc.querySelector('[data-testid="bucket-s-punc"]');
    expect(link).not.toBeNull();
    const href = link!.getAttribute("href") ?? "";
    expect(href).toBe("/learn/skill?skillId=s-punc");
    expect(href).not.toMatch(/\/quiz\?focus=/); // the old drill target is gone
  });
});

describe("BucketCard — honest-absent mastery (P-4 / FR-4)", () => {
  it("known mastery renders a real progressbar with aria-valuenow", () => {
    const doc = dom(<BucketCard vm={card({ masteryKnown: true, masteryPct: 42 })} />);
    const bar = doc.querySelector('[role="progressbar"]');
    expect(bar).not.toBeNull();
    expect(bar!.getAttribute("aria-valuenow")).toBe("42");
    expect(doc.body.textContent ?? "").toMatch(/42%/);
  });

  it("UNKNOWN mastery renders 'no data', NOT a 0% bar (never fabricates)", () => {
    const doc = dom(
      <BucketCard vm={card({ masteryKnown: false, masteryPct: 0 })} />,
    );
    // No progressbar at all — a role=progressbar with aria-valuenow=0 is
    // indistinguishable from a real 0% mastery (the P-4 bug).
    expect(doc.querySelector('[role="progressbar"]')).toBeNull();
    // No fabricated "0%" text; an honest "no data" label instead.
    expect(doc.body.textContent ?? "").not.toMatch(/0%/);
    expect(doc.body.textContent ?? "").toMatch(/no data/i);
  });
});
