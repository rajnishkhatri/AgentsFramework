/**
 * D2 FR-4 — e2e corpus fixture stays in lock-step with DEV_SKILLS.
 *
 * Asserts the 6 canonical labels on the corpus AND that each row agrees with
 * the seed on id / name / key / accent_var / share_of_test_pct / order.
 * Descriptions may differ slightly (corpus is abbreviated) — name + key +
 * accent_var + share + order must match.
 */

import { describe, expect, it } from "vitest";
import { DEV_SKILLS } from "@/lib/adapters/engine/_dev_seed";
import { LEARN_SKILLS } from "./preact_learn_corpus";

const CANONICAL_ID_NAME: ReadonlyArray<readonly [string, string]> = [
  ["s-punc", "Punctuation"],
  ["s-gram", "Usage"],
  ["s-sent", "Sentence Structure"],
  ["s-rhet", "Rhetoric"],
  ["s-org", "Organization"],
  ["s-style", "Conciseness"],
];

describe("preact_learn_corpus — D2 lock-step with DEV_SKILLS (FR-4)", () => {
  it("corpus id→name tuple matches the 6 canonical labels", () => {
    expect(LEARN_SKILLS.map((s) => [s.id, s.name])).toEqual(CANONICAL_ID_NAME);
  });

  it("corpus and seed agree row-by-row on id/name/key/accent_var/share/order", () => {
    expect(LEARN_SKILLS.length).toBe(DEV_SKILLS.length);
    for (let i = 0; i < DEV_SKILLS.length; i++) {
      const seed = DEV_SKILLS[i]!;
      const corpus = LEARN_SKILLS[i]!;
      expect(corpus.id).toBe(seed.id);
      expect(corpus.name).toBe(seed.name);
      expect(corpus.key).toBe(seed.key);
      expect(corpus.accent_var).toBe(seed.accent_var);
      expect(corpus.share_of_test_pct).toBe(seed.share_of_test_pct);
      expect(corpus.order).toBe(seed.order);
    }
  });
});
