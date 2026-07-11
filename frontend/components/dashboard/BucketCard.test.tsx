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
