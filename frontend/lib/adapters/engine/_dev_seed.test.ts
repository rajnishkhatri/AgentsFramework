/**
 * D2 FR-3 + FR-6 — canonical ACT-standard skill display names + untouched
 * non-name fields on every DEV_SKILLS row.
 */

import { describe, expect, it } from "vitest";
import { DEV_SKILLS } from "./_dev_seed";

/** Exact 6-tuple after D2 rename (design-spec.md:62-69). */
const CANONICAL_ID_NAME: ReadonlyArray<readonly [string, string]> = [
  ["s-punc", "Punctuation"],
  ["s-gram", "Usage"],
  ["s-sent", "Sentence Structure"],
  ["s-rhet", "Rhetoric"],
  ["s-org", "Organization"],
  ["s-style", "Conciseness"],
];

/** Non-name fields that MUST NOT mutate (FR-6) — pre-D2 values. */
const CANONICAL_SHAPE: ReadonlyArray<{
  id: string;
  key: string;
  accent_var: string;
  description: string;
  share_of_test_pct: number;
  order: number;
}> = [
  {
    id: "s-punc",
    key: "punctuation",
    accent_var: "--color-bucket-punctuation",
    description: "Commas, semicolons, colons, dashes, and apostrophes.",
    share_of_test_pct: 15,
    order: 1,
  },
  {
    id: "s-gram",
    key: "grammar",
    accent_var: "--color-bucket-usage",
    description: "Subject–verb agreement, pronouns, verb tense, idioms.",
    share_of_test_pct: 20,
    order: 2,
  },
  {
    id: "s-sent",
    key: "sentence",
    accent_var: "--color-bucket-sentence-structure",
    description: "Fragments, run-ons, modifiers, and parallelism.",
    share_of_test_pct: 20,
    order: 3,
  },
  {
    id: "s-rhet",
    key: "rhetoric",
    accent_var: "--color-bucket-rhetoric",
    description: "Word choice, tone, and conciseness in context.",
    share_of_test_pct: 20,
    order: 4,
  },
  {
    id: "s-org",
    key: "organization",
    accent_var: "--color-bucket-organization",
    description: "Transitions, sentence order, and opening/closing sentences.",
    share_of_test_pct: 15,
    order: 5,
  },
  {
    id: "s-style",
    key: "style",
    accent_var: "--color-bucket-conciseness",
    description: "Redundancy, wordiness, and consistent register.",
    share_of_test_pct: 10,
    order: 6,
  },
];

describe("DEV_SKILLS — D2 taxonomy (FR-3, FR-6)", () => {
  it("id→name tuple matches the 6 canonical ACT-standard labels (FR-3)", () => {
    expect(DEV_SKILLS.map((s) => [s.id, s.name])).toEqual(CANONICAL_ID_NAME);
  });

  it("non-name Skill fields are unchanged (FR-6)", () => {
    expect(DEV_SKILLS.length).toBe(CANONICAL_SHAPE.length);
    for (let i = 0; i < CANONICAL_SHAPE.length; i++) {
      const skill = DEV_SKILLS[i]!;
      const expected = CANONICAL_SHAPE[i]!;
      expect(skill.id).toBe(expected.id);
      expect(skill.key).toBe(expected.key);
      expect(skill.accent_var).toBe(expected.accent_var);
      expect(skill.description).toBe(expected.description);
      expect(skill.share_of_test_pct).toBe(expected.share_of_test_pct);
      expect(skill.order).toBe(expected.order);
    }
  });
});
