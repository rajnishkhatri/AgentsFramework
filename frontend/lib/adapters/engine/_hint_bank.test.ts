/**
 * L1 gates for the committed hint bank (coach-bank-hints spec FR-B2/E1).
 *
 * The bank is generated data (cascade-earned; see the module header), so these
 * tests are the merge-time guard that a regeneration, bank re-promotion, or
 * hand edit can't silently ship drifted, malformed, or under-covering ladders:
 *  - parity: `_hint_bank.ts` ↔ the canonical seed JSON (FR-B2 drift pin);
 *  - coverage ratchet: every reviewed bank ITEM has a full 3-rung ladder or an
 *    explicit FR-A3 waiver (FR-E1 — the "bank grows, hints silently lag"
 *    class);
 *  - serving: `seedHintBank` rows reach the reviewed-only read path.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { Hint } from "../../wire/engine_entities";
import { InMemoryEngineDb } from "./db/in_memory_engine_db";
import { HINT_BANK, HINT_BANK_WAIVERS, seedHintBank } from "./_hint_bank";
import { TEST_ITEM_BANK } from "./_test_item_bank";

const SEED_JSON_PATH = resolve(
  __dirname,
  "../../../../docs/plan/coach-bank-hints.seed.json",
);

interface SeedCorpus {
  readonly rows: readonly Hint[];
  readonly waivers: readonly {
    readonly question_id: string;
    readonly rung: 1 | 2 | 3;
    readonly reason: string;
  }[];
}

function loadSeed(): SeedCorpus {
  return JSON.parse(readFileSync(SEED_JSON_PATH, "utf-8")) as SeedCorpus;
}

/** FR-E1 checker, extracted so the ratchet itself is testable red. */
function ladderGaps(
  items: ReadonlyArray<{ id: string; reviewed: boolean }>,
  hints: ReadonlyArray<{ question_id: string; rung: number; reviewed: boolean }>,
  waivers: ReadonlyArray<{ question_id: string; rung: number }>,
): string[] {
  const waived = new Set(waivers.map((w) => `${w.question_id} ${w.rung}`));
  const have = new Set(
    hints.filter((h) => h.reviewed).map((h) => `${h.question_id} ${h.rung}`),
  );
  const gaps: string[] = [];
  for (const item of items) {
    if (!item.reviewed) continue;
    for (const rung of [1, 2, 3]) {
      const key = `${item.id} ${rung}`;
      if (!have.has(key) && !waived.has(key)) gaps.push(key);
    }
  }
  return gaps;
}

describe("HINT_BANK parity with the canonical seed JSON (FR-B2)", () => {
  it("matches the seed rows exactly (count, ids, bodies, rungs, flags)", () => {
    const seed = loadSeed();
    const byKey = (r: Hint) => `${r.question_id} ${r.rung}`;
    const sortedSeed = [...seed.rows].sort((a, b) =>
      byKey(a).localeCompare(byKey(b)),
    );
    const sortedBank = [...HINT_BANK].sort((a, b) =>
      byKey(a).localeCompare(byKey(b)),
    );
    expect(sortedBank).toEqual(sortedSeed);
  });

  it("matches the seed waivers exactly", () => {
    expect([...HINT_BANK_WAIVERS]).toEqual([...loadSeed().waivers]);
  });

  it("every row parses under the Zod Hint schema and is reviewed", () => {
    expect(HINT_BANK.length).toBeGreaterThan(0);
    for (const row of HINT_BANK) {
      expect(Hint.parse(row).reviewed).toBe(true);
    }
  });

  it("every row carries cascade provenance (never a hand-edit marker)", () => {
    for (const row of HINT_BANK) {
      expect(row.generated_by).toMatch(/^[^@\s]+@[^@\s]+$/);
    }
  });
});

describe("coverage ratchet — full ladder per reviewed bank item (FR-E1)", () => {
  it("the checker FINDS a synthetic gap (red anchor — the ratchet can fire)", () => {
    const gaps = ladderGaps(
      [{ id: "ti-gen-synthetic", reviewed: true }],
      [{ question_id: "ti-gen-synthetic", rung: 1, reviewed: true }],
      [],
    );
    expect(gaps).toEqual(["ti-gen-synthetic 2", "ti-gen-synthetic 3"]);
  });

  it("a waiver silences exactly its own gap, nothing else", () => {
    const gaps = ladderGaps(
      [{ id: "ti-gen-synthetic", reviewed: true }],
      [{ question_id: "ti-gen-synthetic", rung: 1, reviewed: true }],
      [{ question_id: "ti-gen-synthetic", rung: 3 }],
    );
    expect(gaps).toEqual(["ti-gen-synthetic 2"]);
  });

  it("every reviewed TEST_ITEM_BANK item has rungs 1-3 (or an FR-A3 waiver)", () => {
    const gaps = ladderGaps(TEST_ITEM_BANK, HINT_BANK, HINT_BANK_WAIVERS);
    expect(
      gaps,
      "bank items shipped without hint ladders — regenerate " +
        "(scripts/generate_hints.py → scripts/emit_hint_bank.py) or add an " +
        "explicit waiver to the seed JSON",
    ).toEqual([]);
  });
});

describe("seedHintBank serving path (FR-C1 substrate)", () => {
  it("loads every ladder behind the reviewed-only read (FR-C3 unchanged)", async () => {
    const db = new InMemoryEngineDb();
    seedHintBank(db);
    for (const item of TEST_ITEM_BANK) {
      const rungs = await db.listReviewedHints("act-english", item.id);
      expect(rungs.map((r) => r.rung)).toEqual([1, 2, 3]);
    }
  });
});
