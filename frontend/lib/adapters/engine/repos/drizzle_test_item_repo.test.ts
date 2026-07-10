/**
 * L2 conformance for DrizzleTestItemRepo + DrizzleTestBlueprintRepo (ADR-0015).
 *
 * The FR-27.1 repo-level gate first (TAP-4): a reviewed=false item MUST NEVER
 * be returned by `listReviewed` — asserted BEFORE the happy path. Runs against
 * the InMemoryEngineDb fake (which enforces the same pushed-down gate as the
 * live seam, the nextReviewedQuestion posture).
 */

import { beforeEach, describe, expect, it } from "vitest";
import { InMemoryEngineDb } from "../db/in_memory_engine_db";
import { DrizzleTestItemRepo } from "./drizzle_test_item_repo";
import { DrizzleTestBlueprintRepo } from "./drizzle_test_blueprint_repo";
import type { TestBlueprint, TestItem } from "../../../wire/engine_entities";

function item(over: Partial<TestItem> = {}): TestItem {
  return {
    id: "ti-1",
    subject: "act-english",
    skill_id: "s-gram",
    difficulty: 3,
    context_html: "The team <u>were</u> ready.",
    stem_md: "Which choice best fixes the underlined portion?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "was ready", is_no_change: false },
      { letter: "C", label: "were readied", is_no_change: false },
      { letter: "D", label: "was readied", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: {
      A: "'Team' acts as one unit — plural clashes.",
      B: "Singular 'was' agrees with the collective 'team'.",
      C: "Still plural, and changes the meaning.",
      D: "'readied' changes the meaning.",
    },
    why_correct_md: "Collective nouns acting as one unit take a singular verb.",
    why_tempted_md: "The people inside the team make 'were' sound right.",
    rule_md: "Collective noun as a unit → singular verb.",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "gpt-4o-mini@run-1",
    ...over,
  };
}

function blueprint(over: Partial<TestBlueprint> = {}): TestBlueprint {
  return {
    id: "bp-1",
    subject: "act-english",
    skill_mix: { "s-gram": 1.0 },
    difficulty_dist: { "3": 1.0 },
    count: 5,
    minutes: 10,
    scale_band_table: [{ raw_min: 0, raw_max: 5, scale: 20 }],
    seed: 7,
    ...over,
  };
}

describe("DrizzleTestItemRepo — reviewed gate first (FR-27.1)", () => {
  let db: InMemoryEngineDb;
  let repo: DrizzleTestItemRepo;

  beforeEach(() => {
    db = new InMemoryEngineDb();
    repo = new DrizzleTestItemRepo(db);
  });

  it("never returns a reviewed=false item", async () => {
    db.seedTestItems([
      item({ id: "ti-unreviewed", reviewed: false }),
      item({ id: "ti-reviewed", reviewed: true }),
    ]);
    const rows = await repo.listReviewed("act-english");
    expect(rows.map((r) => r.id)).toEqual(["ti-reviewed"]);
  });

  it("returns [] when the subject has no reviewed items", async () => {
    db.seedTestItems([item({ reviewed: false })]);
    expect(await repo.listReviewed("act-english")).toEqual([]);
  });

  it("scopes by subject", async () => {
    db.seedTestItems([
      item({ id: "ti-eng", subject: "act-english" }),
      item({ id: "ti-math", subject: "act-math" }),
    ]);
    const rows = await repo.listReviewed("act-english");
    expect(rows.map((r) => r.id)).toEqual(["ti-eng"]);
  });

  it("round-trips the teaching fields (ADR-0021 / FR-C1)", async () => {
    db.seedTestItems([item({ id: "ti-teach" })]);
    const [row] = await repo.listReviewed("act-english");
    expect(row!.context_html).toContain("<u>");
    expect(row!.per_choice_rationale["B"]).toContain("agrees");
    expect(row!.why_correct_md.length).toBeGreaterThan(0);
    expect(row!.why_tempted_md.length).toBeGreaterThan(0);
    expect(row!.rule_md).toContain("singular");
    expect(row!.item_type).toBe("underlined-span-mc");
  });

  it("round-trips misconception null and string (C2 FR-10)", async () => {
    db.seedTestItems([
      item({ id: "ti-mis-null", misconception: null }),
      item({
        id: "ti-mis-str",
        misconception: "confusing simple past with past participle",
      }),
    ]);
    const rows = await repo.listReviewed("act-english");
    const byId = Object.fromEntries(rows.map((r) => [r.id, r]));
    expect(byId["ti-mis-null"]!.misconception).toBeNull();
    expect(byId["ti-mis-str"]!.misconception).toBe(
      "confusing simple past with past participle",
    );
  });
});

describe("DrizzleTestBlueprintRepo", () => {
  let db: InMemoryEngineDb;
  let repo: DrizzleTestBlueprintRepo;

  beforeEach(() => {
    db = new InMemoryEngineDb();
    repo = new DrizzleTestBlueprintRepo(db);
  });

  it("returns null for an unknown id", async () => {
    expect(await repo.get("nope")).toBeNull();
  });

  it("returns the seeded blueprint", async () => {
    db.seedTestBlueprints([blueprint({ id: "bp-x", seed: 99 })]);
    const bp = await repo.get("bp-x");
    expect(bp?.seed).toBe(99);
  });
});
