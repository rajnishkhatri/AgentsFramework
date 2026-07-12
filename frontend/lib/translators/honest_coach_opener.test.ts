/**
 * BP-3c — honest_coach_opener (FR-12 / C4; red-first).
 */

import { describe, expect, it } from "vitest";
import { honestCoachOpener } from "./honest_coach_opener";

const pin = {
  kind: "item" as const,
  questionId: "q1",
  skillId: "s-punc",
  label: "Commas",
};

describe("honestCoachOpener — gate failures first (FR-12)", () => {
  it("returns null when transcript is not empty", () => {
    expect(
      honestCoachOpener({
        pin,
        missesOnSkill: 3,
        transcriptEmpty: false,
      }),
    ).toBeNull();
  });

  it("returns null when pin is null", () => {
    expect(
      honestCoachOpener({
        pin: null,
        missesOnSkill: 3,
        transcriptEmpty: true,
      }),
    ).toBeNull();
  });

  it("returns null when misses are null or zero (no invent)", () => {
    expect(
      honestCoachOpener({ pin, missesOnSkill: null, transcriptEmpty: true }),
    ).toBeNull();
    expect(
      honestCoachOpener({ pin, missesOnSkill: 0, transcriptEmpty: true }),
    ).toBeNull();
  });

  it("never mentions a window / of last 5", () => {
    const text = honestCoachOpener({
      pin,
      missesOnSkill: 3,
      transcriptEmpty: true,
    });
    expect(text).not.toBeNull();
    expect(text!.toLowerCase()).not.toMatch(/last\s*5|window/);
  });
});

describe("honestCoachOpener — happy path", () => {
  it("cites real N and skill label when gate passes", () => {
    const text = honestCoachOpener({
      pin,
      missesOnSkill: 3,
      transcriptEmpty: true,
    });
    expect(text).toContain("3 misses");
    expect(text).toContain("Commas");
  });

  it("singular copy for one miss", () => {
    const text = honestCoachOpener({
      pin,
      missesOnSkill: 1,
      transcriptEmpty: true,
    });
    expect(text).toContain("1 miss on");
    expect(text).not.toContain("1 misses");
  });
});
