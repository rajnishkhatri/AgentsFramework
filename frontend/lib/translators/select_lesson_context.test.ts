/**
 * L1 tests for selectLessonContext (E1a FR-4 / FR-5).
 * Table-driven from design contract §9.2 + AC-2 requested override + AC-3
 * non-due-miss-does-not-flip.
 */

import { describe, expect, it } from "vitest";
import {
  selectLessonContext,
  type LearnerLessonState,
  type LessonContext,
} from "./select_lesson_context";

describe("selectLessonContext — design §9.2 5-row table (FR-4 / AC-1)", () => {
  const rows: ReadonlyArray<{
    name: string;
    state: LearnerLessonState;
    expected: LessonContext;
  }> = [
    {
      name: "firstExposure → newSkill",
      state: { firstExposure: true, masteryPct: null, dueMisses: 0 },
      expected: "newSkill",
    },
    {
      name: "learning (mastery 42, nothing due) → newSkill",
      state: { firstExposure: false, masteryPct: 42, dueMisses: 0 },
      expected: "newSkill",
    },
    {
      name: "returning tagged (mastery 49, 4 due) → returning",
      state: { firstExposure: false, masteryPct: 49, dueMisses: 4 },
      expected: "returning",
    },
    {
      name: "returning untagged (mastery 52, 3 due) → returning",
      state: { firstExposure: false, masteryPct: 52, dueMisses: 3 },
      expected: "returning",
    },
    {
      name: "refresher (mastery 88, 0 due) → refresher",
      state: { firstExposure: false, masteryPct: 88, dueMisses: 0 },
      expected: "refresher",
    },
    {
      // Boundary: `masteryPct >= 80` is inclusive. Exactly 80 → refresher.
      // Pins against an off-by-one mutation to `> 80` (FR-4).
      name: "boundary: mastery EXACTLY 80, 0 due → refresher",
      state: { firstExposure: false, masteryPct: 80, dueMisses: 0 },
      expected: "refresher",
    },
    {
      // Just below the boundary: 79 is not >= 80 and nothing is due → newSkill
      // (the else branch), keeping teaching. Pins the other side of the edge.
      name: "boundary: mastery 79, 0 due → newSkill",
      state: { firstExposure: false, masteryPct: 79, dueMisses: 0 },
      expected: "newSkill",
    },
  ];

  it.each(rows)("$name", ({ state, expected }) => {
    expect(selectLessonContext(state)).toBe(expected);
  });
});

describe("selectLessonContext — AC-2 requested override (FR-4)", () => {
  it("requested wins over firstExposure", () => {
    expect(
      selectLessonContext({
        firstExposure: true,
        masteryPct: null,
        dueMisses: 0,
        requested: "refresher",
      }),
    ).toBe("refresher");
  });

  it("requested wins over dueMisses > 0", () => {
    expect(
      selectLessonContext({
        firstExposure: false,
        masteryPct: 49,
        dueMisses: 4,
        requested: "newSkill",
      }),
    ).toBe("newSkill");
  });
});

describe("selectLessonContext — AC-3 / FR-5 non-due miss does not flip", () => {
  it("dueMisses == 0 stays newSkill even when a tag exists elsewhere", () => {
    // The selector never sees a tag — only dueMisses. A non-due miss with a
    // misconception tag must not route to returning.
    expect(
      selectLessonContext({
        firstExposure: false,
        masteryPct: 42,
        dueMisses: 0,
      }),
    ).toBe("newSkill");
  });

  it("masteryPct == null wins before dueMisses (keep teaching)", () => {
    expect(
      selectLessonContext({
        firstExposure: false,
        masteryPct: null,
        dueMisses: 3,
      }),
    ).toBe("newSkill");
  });
});
