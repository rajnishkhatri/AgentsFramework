/**
 * T26 / V22 — honest_coach_opener grounded invite (FR-12 / C4).
 */

import { describe, expect, it } from "vitest";
import { honestCoachOpener } from "./honest_coach_opener";

const pin = {
  kind: "item" as const,
  questionId: "q1",
  skillId: "s-punc",
  label: "Commas",
};

describe("honestCoachOpener — T26 grounded opener (V22)", () => {
  it("returns null when transcript is not empty", () => {
    expect(
      honestCoachOpener({
        pin,
        missesOnSkill: 3,
        transcriptEmpty: false,
      }),
    ).toBeNull();
  });

  it("empty pin → Ready invite (no fabricated stats)", () => {
    const text = honestCoachOpener({
      pin: null,
      missesOnSkill: 3,
      transcriptEmpty: true,
    });
    expect(text).toMatch(/Ready when you are/i);
    expect(text).not.toMatch(/\d+\s+miss/i);
  });

  it("pin with zero/null misses → Ready invite naming the item, no miss count", () => {
    for (const misses of [null, 0] as const) {
      const text = honestCoachOpener({
        pin,
        missesOnSkill: misses,
        transcriptEmpty: true,
      });
      expect(text).toMatch(/Ready when you are/i);
      expect(text).toContain("Commas");
      expect(text).not.toMatch(/\d+\s+miss/i);
    }
  });

  it("pin + real misses → cites N and skill without inventing a window", () => {
    const text = honestCoachOpener({
      pin,
      missesOnSkill: 3,
      transcriptEmpty: true,
    });
    expect(text).toContain("3 misses");
    expect(text).toContain("Commas");
    expect(text!.toLowerCase()).not.toMatch(/last\s*5|window/);
  });

  it("singular copy for one miss", () => {
    const text = honestCoachOpener({
      pin,
      missesOnSkill: 1,
      transcriptEmpty: true,
    });
    expect(text).toMatch(/1 miss\b/);
    expect(text).not.toContain("1 misses");
  });
});
