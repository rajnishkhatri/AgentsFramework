/**
 * ProgressRepo conformance (ADR-0028, E1a FR-17) — failure paths FIRST.
 *
 * Returns [] (not throw) on no data. Read-only: no write surface.
 */

import { describe, expect, it } from "vitest";
import type { ProgressRepo } from "../../../ports/engine/progress_repo";
import type { ProgressPoint } from "../../../wire/engine_entities";
import { InMemoryEngineDb } from "../db/in_memory_engine_db";
import { DrizzleProgressRepo } from "./drizzle_progress_repo";

const SUBJECT = "act-english";
const LEARNER = "maya";

function point(over: Partial<ProgressPoint> = {}): ProgressPoint {
  return {
    id: "pp-1",
    subject: SUBJECT,
    learner_id: LEARNER,
    at: "2026-07-11T00:00:00.000Z",
    projected_score: 22,
    items_reviewed: 10,
    ...over,
  };
}

describe("DrizzleProgressRepo (against InMemoryEngineDb) — E1a FR-17", () => {
  it("returns [] (not throw) when there is no data", async () => {
    const repo = new DrizzleProgressRepo(new InMemoryEngineDb());
    expect(await repo.list(SUBJECT, LEARNER)).toEqual([]);
  });

  it("returns seeded progress points for the learner", async () => {
    const db = new InMemoryEngineDb();
    db.seedProgress([
      point({ id: "pp-1", projected_score: 20 }),
      point({ id: "pp-2", projected_score: 24, at: "2026-07-12T00:00:00.000Z" }),
    ]);
    const repo = new DrizzleProgressRepo(db);
    const got = await repo.list(SUBJECT, LEARNER);
    expect(got).toHaveLength(2);
    expect(got.map((p) => p.id).sort()).toEqual(["pp-1", "pp-2"]);
  });

  it("scopes by subject and learner", async () => {
    const db = new InMemoryEngineDb();
    db.seedProgress([
      point({ id: "pp-a" }),
      point({ id: "pp-b", subject: "act-math" }),
      point({ id: "pp-c", learner_id: "other" }),
    ]);
    const repo = new DrizzleProgressRepo(db);
    const got = await repo.list(SUBJECT, LEARNER);
    expect(got).toHaveLength(1);
    expect(got[0]!.id).toBe("pp-a");
  });
});

describe("ProgressRepo port — read-only (FR-17)", () => {
  it("has no write method on the interface type", () => {
    const stub: ProgressRepo = {
      list: async () => [],
    };
    expect(Object.keys(stub)).toEqual(["list"]);
    // @ts-expect-error — no insertProgress on ProgressRepo
    expect(stub.insertProgress).toBeUndefined();
  });
});
