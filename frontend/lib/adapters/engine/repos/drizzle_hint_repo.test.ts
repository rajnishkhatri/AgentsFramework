/**
 * HintRepo conformance (ADR-0014, spec FR-12/FR-20) — failure paths FIRST.
 *
 * The hard invariant this bundle pins: an ungated (`reviewed = false`) rung is
 * NEVER served, enforced in the store AND re-checked in the repo (the
 * `nextReviewed` double-enforcement posture). The assertion rung (4) is
 * unrepresentable at the wire. Runs against `InMemoryEngineDb` — the same
 * `EngineDb` contract the live Drizzle seam implements.
 */

import { describe, expect, it } from "vitest";

import { Hint } from "../../../wire/engine_entities";
import { InMemoryEngineDb } from "../db/in_memory_engine_db";
import { DrizzleHintRepo } from "./drizzle_hint_repo";

const SUBJECT = "act-english";

function rung(overrides: Partial<Hint> = {}): Hint {
  return {
    id: `h-${Math.random().toString(36).slice(2, 10)}`,
    subject: SUBJECT,
    question_id: "q-punc-1",
    rung: 1,
    body_md: "What job is the clause doing in this sentence?",
    reviewed: true,
    generated_by: "authored",
    ...overrides,
  };
}

describe("Hint wire entity", () => {
  it("rejects the assertion rung (4) — unrepresentable, ADR-0012", () => {
    expect(Hint.safeParse(rung({ rung: 4 as never })).success).toBe(false);
    expect(Hint.safeParse(rung({ rung: 0 as never })).success).toBe(false);
  });

  it("rejects an empty body", () => {
    expect(Hint.safeParse(rung({ body_md: "" })).success).toBe(false);
  });

  it("accepts rungs 1..3", () => {
    for (const r of [1, 2, 3] as const) {
      expect(Hint.safeParse(rung({ rung: r })).success).toBe(true);
    }
  });
});

describe("DrizzleHintRepo (against InMemoryEngineDb)", () => {
  it("NEVER serves an unreviewed rung (FR-12)", async () => {
    const db = new InMemoryEngineDb();
    db.seedHints([
      rung({ rung: 1, reviewed: true }),
      rung({ rung: 2, reviewed: false, generated_by: "gpt-4o-mini@run-1" }),
      rung({ rung: 3, reviewed: true }),
    ]);
    const repo = new DrizzleHintRepo(db);
    const served = await repo.list(SUBJECT, "q-punc-1");
    expect(served.map((h) => h.rung)).toEqual([1, 3]);
    expect(served.every((h) => h.reviewed)).toBe(true);
  });

  it("returns [] rather than throwing for an unknown question", async () => {
    const repo = new DrizzleHintRepo(new InMemoryEngineDb());
    expect(await repo.list(SUBJECT, "q-nope")).toEqual([]);
  });

  it("scopes by subject AND question", async () => {
    const db = new InMemoryEngineDb();
    db.seedHints([
      rung({ question_id: "q-punc-1" }),
      rung({ question_id: "q-gram-1" }),
      rung({ subject: "act-math", question_id: "q-punc-1", rung: 2 }),
    ]);
    const repo = new DrizzleHintRepo(db);
    const served = await repo.list(SUBJECT, "q-punc-1");
    expect(served).toHaveLength(1);
    expect(served[0]?.question_id).toBe("q-punc-1");
    expect(served[0]?.subject).toBe(SUBJECT);
  });

  it("orders the ladder by rung ascending (probe -> directive)", async () => {
    const db = new InMemoryEngineDb();
    db.seedHints([
      rung({ rung: 3, body_md: "directive" }),
      rung({ rung: 1, body_md: "probe" }),
      rung({ rung: 2, body_md: "conceptual" }),
    ]);
    const repo = new DrizzleHintRepo(db);
    const served = await repo.list(SUBJECT, "q-punc-1");
    expect(served.map((h) => h.rung)).toEqual([1, 2, 3]);
  });

  it("rejects a duplicate (question_id, rung) insert — one rung per level", async () => {
    const db = new InMemoryEngineDb();
    await db.insertHint(rung({ rung: 1 }));
    await expect(db.insertHint(rung({ rung: 1 }))).rejects.toThrow();
  });
});

describe("dev seed ladder", () => {
  it("seeds one full reviewed ladder (rungs 1..3) per dev question", async () => {
    const { InMemoryEngineDb: Db } = await import("../db/in_memory_engine_db");
    const { seedDevCorpus } = await import("../_dev_seed");
    const db = new Db();
    seedDevCorpus(db);
    const repo = new DrizzleHintRepo(db);
    for (const qid of [
      "q-punc-1",
      "q-gram-1",
      "q-sent-1",
      "q-rhet-1",
      "q-org-1",
      "q-style-1",
    ]) {
      const ladder = await repo.list(SUBJECT, qid);
      expect(ladder.map((h) => h.rung)).toEqual([1, 2, 3]);
      expect(ladder.every((h) => h.generated_by === "authored")).toBe(true);
    }
  });
});
