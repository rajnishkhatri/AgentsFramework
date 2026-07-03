/**
 * L1 roundtrip: the committed Test-01 corpus → governed-bank seed (FR-25.2/25.3).
 *
 * This is the OFFLINE half of the 6.11 live gate — it proves the import path
 * mechanically against the real 48-row committed corpus (the tracked oracle,
 * present in CI), leaving only the live-LLM solver pass for the on-demand
 * human-run generator check. It asserts:
 *   - all 48 committed rows demote cleanly to reviewed=false seed rows,
 *   - each seed row parses under the Zod `TestItem` schema (shape closure
 *     across the TS→Python boundary the Python cascade re-verifies), and
 *   - the declared key on every seed row is one of its own choice letters
 *     (so the Python solver gate has a well-formed candidate to confirm).
 *
 * The committed corpus is byte-frozen (FR-25.3); this reads it, never writes.
 */

import { describe, expect, it } from "vitest";
import { TEST01_ENGLISH_QUESTIONS } from "../lib/adapters/engine/_test01_english_corpus";
import { toTestItemSeed, TEST01_IMPORT_PROVENANCE } from "./convert_test01_seed";
import { TestItem } from "../lib/wire/engine_entities";

describe("Test-01 corpus → governed-bank seed roundtrip (6.11 offline half)", () => {
  const seed = toTestItemSeed(TEST01_ENGLISH_QUESTIONS);

  it("demotes all 48 committed rows to reviewed=false seed rows", () => {
    expect(seed).toHaveLength(48);
    expect(seed.every((r) => r.reviewed === false)).toBe(true);
    expect(seed.every((r) => r.generated_by === TEST01_IMPORT_PROVENANCE)).toBe(true);
  });

  it("every seed row parses under the Zod TestItem schema (boundary closure)", () => {
    for (const row of seed) {
      expect(() => TestItem.parse(row)).not.toThrow();
    }
  });

  it("every seed row's declared key is one of its own choice letters", () => {
    for (const row of seed) {
      const letters = row.choices.map((c) => c.letter);
      expect(letters).toContain(row.answer_letter);
    }
  });
});
