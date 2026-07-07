/**
 * L1 gates for the committed practice bank (ADR-0021, spec FR-B1/FR-A6).
 *
 * The bank is generated data (cascade-promoted; see the module docstring), so
 * these tests are the merge-time guard that a re-generation or hand edit can't
 * silently ship a malformed or under-covering bank.
 */

import { describe, expect, it } from "vitest";
import { TestItem } from "../../wire/engine_entities";
import { InMemoryEngineDb } from "./db/in_memory_engine_db";
import { seedTestItemBank, TEST_ITEM_BANK } from "./_test_item_bank";

const SIX_SKILLS = ["s-punc", "s-gram", "s-sent", "s-rhet", "s-org", "s-style"];

describe("TEST_ITEM_BANK (FR-B1)", () => {
  it("every row parses under the Zod TestItem schema and is reviewed", () => {
    expect(TEST_ITEM_BANK.length).toBeGreaterThan(0);
    for (const row of TEST_ITEM_BANK) {
      const parsed = TestItem.parse(row);
      expect(parsed.reviewed).toBe(true);
    }
  });

  it("every row carries cascade provenance, never an authoring marker (FR-B7)", () => {
    for (const row of TEST_ITEM_BANK) {
      expect(row.generated_by).toMatch(/^[^@\s]+@[^@\s]+$/);
      expect(row.generated_by).not.toContain("claude-session-authored");
      expect(row.generated_by).not.toContain("test01-import");
    }
  });

  it("covers all six ACT-English skills (FR-A6)", () => {
    const covered = new Set(TEST_ITEM_BANK.map((r) => r.skill_id));
    for (const skill of SIX_SKILLS) {
      expect(covered, `missing reviewed item for ${skill}`).toContain(skill);
    }
  });

  it("seedTestItemBank loads every row into the engine db (FR-B1)", async () => {
    const db = new InMemoryEngineDb();
    seedTestItemBank(db);
    const rows = await db.listReviewedTestItems("act-english");
    expect(rows).toHaveLength(TEST_ITEM_BANK.length);
  });
});
