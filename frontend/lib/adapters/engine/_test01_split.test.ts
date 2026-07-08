/**
 * D2 Test-01 split (docs/plan/test01-practice-split.spec.md).
 *
 * FR-1 exclusivity guard — the point of D2, it outlives the split: no
 * normalized stem may appear in BOTH the practice bank and the served timed
 * test. The detector-anchor test proves the guard catches a seeded overlap
 * (the `test_detector_flags_a_self_stamped…` house pattern — the honest
 * "seen to fail first" for a guard whose real surfaces are clean today).
 *
 * FR-2/FR-4 manifest — the committed docs/plan/test01-split-manifest.json is
 * the audit source of truth; the TS mirror in `_test01_split.ts` is pinned
 * against it byte-for-byte here (drift fails). Partition: every corpus row
 * has exactly one fate. Balance: promoted ≈ half per skill (±1).
 *
 * FR-6/FR-7 filter — the timed test serves ONLY test_only rows, corpus order
 * preserved, minutes scaled; a non-empty section is asserted at module load.
 */
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { TEST01_ENGLISH_QUESTIONS } from "./_test01_english_corpus";
import {
  TEST01_PROMOTED_IDS,
  TEST01_SERVED_MINUTES,
  TEST01_SERVED_QUESTIONS,
  TEST01_TEST_ONLY_IDS,
  stemOverlap,
} from "./_test01_split";
import { TEST_ITEM_BANK } from "./_test_item_bank";

const MANIFEST_PATH = new URL(
  "../../../../docs/plan/test01-split-manifest.json",
  import.meta.url,
);

describe("manifest partition (FR-2/FR-4)", () => {
  it("TS mirror matches the committed docs/plan manifest exactly", () => {
    const manifest = JSON.parse(readFileSync(MANIFEST_PATH, "utf-8")) as {
      promoted: string[];
      test_only: string[];
    };
    expect([...TEST01_PROMOTED_IDS]).toEqual(manifest.promoted);
    expect([...TEST01_TEST_ONLY_IDS]).toEqual(manifest.test_only);
  });

  it("every corpus row has exactly one fate", () => {
    const promoted = new Set<string>(TEST01_PROMOTED_IDS);
    const testOnly = new Set<string>(TEST01_TEST_ONLY_IDS);
    const corpusIds = TEST01_ENGLISH_QUESTIONS.map((q) => q.id);
    for (const id of promoted) expect(testOnly.has(id)).toBe(false);
    expect(
      [...promoted, ...testOnly].sort((a, b) => a.localeCompare(b)),
    ).toEqual([...corpusIds].sort((a, b) => a.localeCompare(b)));
  });

  it("promoted is balanced ~half per skill (±1)", () => {
    const promoted = new Set<string>(TEST01_PROMOTED_IDS);
    const perSkill = new Map<string, { total: number; promoted: number }>();
    for (const q of TEST01_ENGLISH_QUESTIONS) {
      const cell = perSkill.get(q.skill_id) ?? { total: 0, promoted: 0 };
      cell.total += 1;
      if (promoted.has(q.id)) cell.promoted += 1;
      perSkill.set(q.skill_id, cell);
    }
    for (const [skill, { total, promoted: n }] of perSkill) {
      expect(
        Math.abs(n - total / 2),
        `${skill}: ${n} promoted of ${total}`,
      ).toBeLessThanOrEqual(1);
    }
  });
});

describe("served timed test (FR-6/FR-7)", () => {
  it("serves ONLY test_only rows, corpus order preserved", () => {
    const testOnly = new Set<string>(TEST01_TEST_ONLY_IDS);
    expect(TEST01_SERVED_QUESTIONS.map((q) => q.id)).toEqual(
      TEST01_ENGLISH_QUESTIONS.filter((q) => testOnly.has(q.id)).map(
        (q) => q.id,
      ),
    );
  });

  it("minutes scale with the served count (ceil, never a shorter pace)", () => {
    expect(TEST01_SERVED_MINUTES).toBe(
      Math.ceil((35 * TEST01_SERVED_QUESTIONS.length) / 48),
    );
    expect(TEST01_SERVED_MINUTES).toBe(18);
  });

  it("the section is never empty (FR-7 load assert backs this)", () => {
    expect(TEST01_SERVED_QUESTIONS.length).toBeGreaterThan(0);
  });
});

describe("practice/test exclusivity guard (FR-1)", () => {
  it("detector catches a seeded overlap (guard-detects-the-thing anchor)", () => {
    const overlap = stemOverlap(
      ["Which  choice BEST fixes the sentence?"],
      ["which choice best fixes the sentence?"],
    );
    expect(overlap).toHaveLength(1);
  });

  it("normalization is real, not exact-match theater", () => {
    expect(stemOverlap(["a  b"], ["c d"])).toHaveLength(0);
  });

  it("no stem appears in BOTH the practice bank and the served test", () => {
    const bankStems = TEST_ITEM_BANK.map((row) => row.stem_md);
    const servedStems = TEST01_SERVED_QUESTIONS.map((q) => q.stem);
    expect(stemOverlap(bankStems, servedStems)).toEqual([]);
  });
});
