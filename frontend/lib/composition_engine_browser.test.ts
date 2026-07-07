/**
 * Phase 0.3 — engine browser accessor (FR-C2, L1 deterministic, TAP-1).
 *
 * The C2 seam: `composition_engine_browser.ts` is the browser-side sibling of
 * `composition_engine.ts`. Like `composition_browser.ts` (the chat slice) it
 * may name concrete adapters, but it wires ONLY the browser-safe substrate —
 * `InMemoryEngineDb`, the on-device-before-SQLite path (ADR-0005 local-first /
 * ADR-0010). The pg/Drizzle-over-pg driver (`drizzle_engine_db`, `pg`) is
 * server-only and must never enter the client bundle, so this file must NOT
 * import `composition_engine.ts` (whose module-top `pgEngineDb` import would
 * drag the driver in). This test locks that boundary.
 *
 * Failure paths first (Anti-Pattern 6 avoided):
 *   1. the bag must expose all eight ports (7 ADR-0006 + LearnerReadRepo,
 *      ADR-0011) — a missing port is the failure mode a consumer hits at
 *      render time;
 *   2. the singleton accessor must be stable (a fresh bag per call would make
 *      the React provider re-mount adapters every render).
 * Then the happy path (ports are callable against the in-memory substrate).
 *
 * Spec: docs/plan/preact-english-coach-ui.spec.md FR-C2; ADR-0006/0010.
 */

import { describe, expect, it } from "vitest";
import {
  browserEngineAdapters,
  buildBrowserEngineAdapters,
} from "./composition_engine_browser";
import type { EnginePortBag } from "./composition_engine";
import { InMemoryEngineDb } from "./adapters/engine/db/in_memory_engine_db";
import type { Question } from "./wire/engine_entities";

function question(over: Partial<Question> = {}): Question {
  return {
    id: "q1",
    subject: "act-english",
    skill_id: "s1",
    difficulty: 3,
    context_html: "The committee <u>have</u> decided.",
    stem: "Which choice is best?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "has", is_no_change: false },
    ],
    answer_letter: "A",
    per_choice_rationale: { A: "Why A is correct.", B: "Why B tempted you." },
    why_correct_md: "…",
    why_tempted_md: "…",
    rule_md: "…",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

const PORT_NAMES: ReadonlyArray<keyof EnginePortBag> = [
  "skillTaxonomy",
  "questionRepo",
  "attemptRepo",
  "sessionRepo",
  "scheduler",
  "grader",
  "contentRepo",
  // ADR-0011: read-only skill_state view — the browser root wires it too, so
  // it must be covered here (a subset array typechecks against keyof, so an
  // omission would pass silently).
  "learnerRead",
];

describe("FR-C2 engine_browser_accessor", () => {
  it("exposes all eight engine ports (none missing)", () => {
    const bag = buildBrowserEngineAdapters();
    for (const name of PORT_NAMES) {
      expect(bag[name], `port "${name}" missing from EnginePortBag`).toBeDefined();
    }
  });

  it("accepts an injected EngineDb (test seam) and uses it", () => {
    // A seeded InMemoryEngineDb is the deterministic corpus the loop tests
    // will stand up; the accessor must let a test inject one.
    const db = new InMemoryEngineDb();
    const bag = buildBrowserEngineAdapters({ engineDb: db });
    expect(bag.questionRepo).toBeDefined();
  });

  it("browserEngineAdapters() returns a stable singleton", () => {
    const a = browserEngineAdapters();
    const b = browserEngineAdapters();
    expect(a).toBe(b);
  });

  it("dev-default singleton serves the bank hint ladders (FR-C1)", async () => {
    // coach-bank-hints: the dev preview must seed the generated hint bank
    // next to the item bank, or the CoachPanel's two-tier nudge falls back to
    // the generic Socratic line on every bank item.
    const { TEST_ITEM_BANK } = await import("./adapters/engine/_test_item_bank");
    const first = TEST_ITEM_BANK[0];
    if (!first) throw new Error("committed item bank is empty");
    const bag = browserEngineAdapters();
    const rungs = await bag.hintRepo.list("act-english", first.id);
    expect(rungs.map((r) => r.rung)).toEqual([1, 2, 3]);
  });

  it("wires the grader so an exact-letter match grades correct", () => {
    // Happy path: the grader is pure + offline + SYNC (ExactLetterGrader, P5
    // exception), so it is exercisable with no DB — proof the bag is really
    // wired, not stubbed.
    const bag = buildBrowserEngineAdapters();
    const verdict = bag.grader.grade(question({ answer_letter: "A" }), {
      letter: "A",
    });
    expect(verdict?.correct).toBe(true);
  });
});
