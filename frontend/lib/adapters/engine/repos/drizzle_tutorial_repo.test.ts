/**
 * TutorialRepo conformance (ADR-0028, E1a FR-1 / FR-17) — failure paths FIRST.
 *
 * Hard invariant: an unreviewed tutorial row is NEVER served. Defense-in-depth
 * filter in the repo even if the store seam regresses. Read-only: no write
 * surface on the port. Runs against InMemoryEngineDb.
 */

import { describe, expect, it } from "vitest";
import type { TutorialRepo } from "../../../ports/engine/tutorial_repo";
import type { Tutorial } from "../../../wire/engine_entities";
import { InMemoryEngineDb } from "../db/in_memory_engine_db";
import { DrizzleTutorialRepo } from "./drizzle_tutorial_repo";

const SUBJECT = "act-english";

function tutorial(over: Partial<Tutorial> = {}): Tutorial {
  return {
    id: "tut-1",
    subject: SUBJECT,
    skill_id: "s-nec",
    body_md: "Fence non-essential clauses with a pair of commas.",
    examples: ["My car, which is electric, is quiet."],
    generated_from: "hand:author@2026-07-11",
    reviewed: true,
    ...over,
  };
}

describe("DrizzleTutorialRepo (against InMemoryEngineDb) — E1a FR-1", () => {
  it("NEVER serves an unreviewed tutorial (FR-1)", async () => {
    const db = new InMemoryEngineDb();
    db.seedTutorial(tutorial({ reviewed: false, generated_from: "forged" }));
    const repo = new DrizzleTutorialRepo(db);
    expect(await repo.getTutorial(SUBJECT, "s-nec")).toBeNull();
  });

  it("returns the reviewed tutorial for a known skill", async () => {
    const db = new InMemoryEngineDb();
    const row = tutorial({
      ground_md: "You know list commas.",
      reviewed: true,
    });
    db.seedTutorial(row);
    const repo = new DrizzleTutorialRepo(db);
    const got = await repo.getTutorial(SUBJECT, "s-nec");
    expect(got).not.toBeNull();
    expect(got!.reviewed).toBe(true);
    expect(got!.ground_md).toBe("You know list commas.");
  });

  it("returns null (not throw) for an unknown skill (FR-18)", async () => {
    const repo = new DrizzleTutorialRepo(new InMemoryEngineDb());
    expect(await repo.getTutorial(SUBJECT, "s-nope")).toBeNull();
  });

  it("scopes by subject", async () => {
    const db = new InMemoryEngineDb();
    db.seedTutorial(tutorial({ subject: "act-math" }));
    const repo = new DrizzleTutorialRepo(db);
    expect(await repo.getTutorial(SUBJECT, "s-nec")).toBeNull();
  });
});

describe("TutorialRepo port — read-only (FR-17)", () => {
  it("has no write method on the interface type", () => {
    // Compile-time proxy: assign a conforming object; a write method would not
    // be required (and must not exist on the type for callers to use).
    const stub: TutorialRepo = {
      getTutorial: async () => null,
    };
    expect(Object.keys(stub)).toEqual(["getTutorial"]);
    // @ts-expect-error — no insertTutorial on TutorialRepo
    expect(stub.insertTutorial).toBeUndefined();
  });
});
