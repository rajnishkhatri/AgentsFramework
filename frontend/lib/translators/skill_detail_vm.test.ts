/**
 * L1 tests for toSkillDetailVM (E1a FR-6a/c/d, FR-7..10).
 * Failure paths and recipe-order assertions first.
 */

import { describe, expect, it } from "vitest";
import type { Skill, Tutorial } from "../wire/engine_entities";
import {
  __MAIN_RECIPES_FOR_TEST,
  toSkillDetailVM,
  type BlockVM,
} from "./skill_detail_vm";

const SKILL: Skill = {
  id: "s-punc",
  subject: "act-english",
  key: "punctuation",
  name: "Punctuation",
  share_of_test_pct: 15,
  accent_var: "--color-bucket-punctuation",
  description: "",
  order: 1,
};

function tutorial(over: Partial<Tutorial> = {}): Tutorial {
  return {
    id: "tut-1",
    subject: "act-english",
    skill_id: "s-punc",
    body_md: "Run the removal test.",
    examples: ["My kitchen, which provides an alternative to eating out, is small."],
    generated_from: "hand:rajnish@2026-07-11",
    reviewed: true,
    ground_md: "You already use commas.",
    pitfall_md: "A pair vs none flips meaning.",
    question_md: "How do you tell when a clause needs commas?",
    self_explain_prompt: "When do you think a clause needs commas?",
    worked_example: {
      sentence: "My kitchen, which provides an alternative to eating out, is small.",
      steps: ["Remove.", "Non-essential.", "Fence."],
      answer: "Keep both commas.",
    },
    completion_try: {
      sentence: "The teacher, who grades fairly, is popular.",
      choices: [
        { text: "Keep both commas", correct: true },
        { text: "Delete the commas", correct: false },
      ],
      why: "Still stands → keep both.",
    },
    annotated_examples: [
      {
        pre: "My kitchen",
        clause: "which provides an alternative to eating out",
        post: " is small.",
        essential: false,
        callouts: ["remove it → still works"],
      },
    ],
    ...over,
  };
}

function mainTags(blocks: readonly BlockVM[]): string[] {
  return blocks.map((b) => b.tag);
}

describe("toSkillDetailVM — newSkill (FR-7 / FR-8b / FR-9 / FR-10)", () => {
  it("FR-7: newSkill recipe order, no other blocks", () => {
    const vm = toSkillDetailVM({
      context: "newSkill",
      tutorial: tutorial(),
      skill: SKILL,
      misconceptionTag: null,
      dueSkills: [],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    expect(mainTags(vm.main)).toEqual([
      "ground",
      "pitfall",
      "question",
      "selfExplainPrompt",
      "rule",
      "workedExample",
      "completionTry",
    ]);
    expect(vm.rail).toEqual([]); // accuracyStat self-omits (FR-16)
  });

  it("FR-8b: order comes from the recipe map, not a persisted array", () => {
    expect(__MAIN_RECIPES_FOR_TEST.newSkill).toEqual([
      "ground",
      "pitfall",
      "question",
      "selfExplainPrompt",
      "rule",
      "workedExample",
      "completionTry",
    ]);
    // Tutorial has no blocks/zone/role fields — composer derives order.
    const raw = tutorial() as Tutorial & { blocks?: unknown };
    expect(raw.blocks).toBeUndefined();
  });

  it("FR-9: a tag with no backing field is skipped (no empty VM)", () => {
    const vm = toSkillDetailVM({
      context: "newSkill",
      tutorial: tutorial({ ground_md: undefined, pitfall_md: "trap" }),
      skill: SKILL,
      misconceptionTag: null,
      dueSkills: [],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    expect(mainTags(vm.main)[0]).toBe("pitfall");
    expect(vm.main.every((b) => b.tag !== "ground")).toBe(true);
  });

  it("FR-10: main zone ends on completionTry, never on pitfall pre-rule", () => {
    const vm = toSkillDetailVM({
      context: "newSkill",
      tutorial: tutorial(),
      skill: SKILL,
      misconceptionTag: null,
      dueSkills: [],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    expect(vm.main[vm.main.length - 1]!.tag).toBe("completionTry");
    const pitfallIdx = vm.main.findIndex((b) => b.tag === "pitfall");
    const ruleIdx = vm.main.findIndex((b) => b.tag === "rule");
    expect(pitfallIdx).toBeGreaterThanOrEqual(0);
    expect(ruleIdx).toBeGreaterThan(pitfallIdx);
  });

  it("honest empty when tutorial is null (FR-3 / FR-18)", () => {
    const vm = toSkillDetailVM({
      context: "newSkill",
      tutorial: null,
      skill: SKILL,
      misconceptionTag: null,
      dueSkills: [],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    expect(vm.empty).toBe(true);
    expect(vm.main).toEqual([]);
  });
});

describe("toSkillDetailVM — returning / refresher (FR-6a / FR-6c / FR-6d)", () => {
  it("FR-6a: returning tagged → misc→annotated→rule", () => {
    const vm = toSkillDetailVM({
      context: "returning",
      tutorial: tutorial(),
      skill: SKILL,
      misconceptionTag: "deleting commas to shorten a which-clause",
      dueSkills: [{ skillId: "s-gram", name: "Usage" }],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    expect(mainTags(vm.main)).toEqual([
      "misconceptionCallout",
      "annotatedExample",
      "rule",
    ]);
    expect(vm.main[vm.main.length - 1]!.tag).toBe("rule");
  });

  it("FR-6a/c: returning untagged → annotated→rule; no callout, no miss-count", () => {
    const vm = toSkillDetailVM({
      context: "returning",
      tutorial: tutorial(),
      skill: SKILL,
      misconceptionTag: null,
      dueSkills: [{ skillId: "s-gram", name: "Usage" }],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    expect(mainTags(vm.main)).toEqual(["annotatedExample", "rule"]);
    expect(vm.main.every((b) => b.tag !== "misconceptionCallout")).toBe(true);
  });

  it("FR-6c: returning with whitespace-only tag → callout hides (trim clause)", () => {
    // Pins the `.trim() === ""` half of the hide guard — distinct from the
    // null case above. A mutation dropping the trim clause would render a
    // callout with a blank body.
    const vm = toSkillDetailVM({
      context: "returning",
      tutorial: tutorial(),
      skill: SKILL,
      misconceptionTag: "   ",
      dueSkills: [{ skillId: "s-gram", name: "Usage" }],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    expect(mainTags(vm.main)).toEqual(["annotatedExample", "rule"]);
    expect(vm.main.every((b) => b.tag !== "misconceptionCallout")).toBe(true);
  });

  it("GUARD-END-1: newSkill with only ground+pitfall authored must NOT end on pitfall (no rule above it)", () => {
    // A partial seed (ground + pitfall only) would let the pure recipe walk end
    // on a tension block with no rule/resolution above it — the AL-13 block-layer
    // guard forbids this (Adaptive-Lesson-Protocol §AL-13 / Decisions §D2). The
    // composer must drop the trailing unresolved tension block, never leave the
    // learner staring at a trap with no way out.
    const partial: Tutorial = {
      id: "tut-partial",
      subject: "act-english",
      skill_id: "s-punc",
      body_md: "", // no rule content
      examples: [],
      generated_from: "hand:rajnish@2026-07-11",
      reviewed: true,
      ground_md: "You already use commas.",
      pitfall_md: "A pair vs none flips meaning.",
    };
    const vm = toSkillDetailVM({
      context: "newSkill",
      tutorial: partial,
      skill: SKILL,
      misconceptionTag: null,
      dueSkills: [],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    const last = vm.main[vm.main.length - 1];
    // The main zone must not end on an unresolved tension block.
    const TENSION = new Set(["pitfall", "misconceptionCallout"]);
    const hasRule = vm.main.some((b) => b.tag === "rule");
    if (last != null && TENSION.has(last.tag)) {
      expect(hasRule).toBe(true); // ending on tension is only OK if rule appeared above
    }
    // Concretely for this fixture: no rule authored → pitfall must be dropped.
    expect(vm.main.map((b) => b.tag)).not.toContain("pitfall");
  });

  it("FR-6d: refresher → rule→annotated→pitfall(parting), ends on parting pitfall", () => {
    const vm = toSkillDetailVM({
      context: "refresher",
      tutorial: tutorial(),
      skill: SKILL,
      misconceptionTag: null,
      dueSkills: [],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    expect(mainTags(vm.main)).toEqual(["rule", "annotatedExample", "pitfall"]);
    const last = vm.main[vm.main.length - 1]!;
    expect(last.tag).toBe("pitfall");
    if (last.tag === "pitfall") expect(last.framing).toBe("parting");
  });

  it("returning rail: dueChecklist + coachEntry; accuracyStat self-omits (FR-6e / FR-16)", () => {
    const vm = toSkillDetailVM({
      context: "returning",
      tutorial: tutorial(),
      skill: SKILL,
      misconceptionTag: "a tag",
      // Cross-skill rail: the producer (dueSkillRows) excludes the current skill
      // (s-punc), so dueSkills carries OTHER due skills only.
      dueSkills: [
        { skillId: "s-gram", name: "Usage" },
        { skillId: "s-sent", name: "Sentence structure" },
      ],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    expect(vm.rail.map((b) => b.tag)).toEqual(["dueChecklist", "coachEntry"]);
  });

  it("FR-6b proxy: callout body is verbatim misconceptionTag", () => {
    const tag = "deleting commas to shorten a which-clause";
    const vm = toSkillDetailVM({
      context: "returning",
      tutorial: tutorial(),
      skill: SKILL,
      misconceptionTag: tag,
      dueSkills: [],
      accuracy: null,
      nowISO: "2026-07-11T12:00:00.000Z",
    });
    const callout = vm.main.find((b) => b.tag === "misconceptionCallout");
    expect(callout).toBeDefined();
    if (callout?.tag === "misconceptionCallout") {
      expect(callout.body).toBe(tag);
      expect(callout.eyebrow).toBe("On your last miss · Punctuation");
    }
  });
});
