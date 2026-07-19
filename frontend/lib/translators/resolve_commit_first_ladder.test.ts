/**
 * FR-8 — commit-first ladder fallback chain (L1).
 */

import { describe, expect, it } from "vitest";
import { resolveCommitFirstLadder } from "./resolve_commit_first_ladder";
import type { Hint } from "../wire/engine_entities";

function hint(over: Partial<Hint> & { id: string; rung: 1 | 2 | 3 }): Hint {
  return {
    subject: "act-english",
    question_id: "q1",
    choice_letter: null,
    body_md: "nudge",
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

describe("resolveCommitFirstLadder — FR-8 fallback chain", () => {
  it("prefers the choice-keyed ladder when present", async () => {
    const choice = [hint({ id: "c1", rung: 1, choice_letter: "A", body_md: "choice" })];
    const got = await resolveCommitFirstLadder(
      async (letter) => (letter === "A" ? choice : []),
      "A",
      "generic",
      "q1",
      "act-english",
    );
    expect(got).toEqual(choice);
  });

  it("falls back to item-level when choice ladder is empty", async () => {
    const item = [hint({ id: "i1", rung: 1, body_md: "item" })];
    const got = await resolveCommitFirstLadder(
      async (letter) => (letter == null ? item : []),
      "A",
      "generic",
      "q1",
      "act-english",
    );
    expect(got).toEqual(item);
  });

  it("falls back to a single-rung generic when both are empty", async () => {
    const got = await resolveCommitFirstLadder(
      async () => [],
      "A",
      "Before you pick: re-read the stem",
      "q1",
      "act-english",
    );
    expect(got).toHaveLength(1);
    expect(got[0]?.rung).toBe(1);
    expect(got[0]?.body_md).toContain("re-read");
  });
});
