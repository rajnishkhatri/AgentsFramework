/**
 * Phase 1.6 — Summary orchestration (FR-G1..G3, L1 deterministic).
 *
 * Per F-R1 the Summary component owns NO domain logic. Reading the STORED
 * session score (never a re-tally, FR-G1), diffing the mastery snapshot against
 * a fresh read for the delta (ADR-0011 §4), and picking the recommended-next
 * skill (FR-G1/G2) all live here, in the React-free `loadSummary` exercised in
 * node against a seeded InMemoryEngineDb.
 *
 * READ-ONLY (FR-A2): Summary is a *view* — it reads via `sessionRepo.get` +
 * `learnerRead.listSkillState` and never writes skill_state (no scheduler.next).
 *
 * Failure/edge path first: an absent start-snapshot for the focus skill (a
 * brand-new learner) makes the delta UNKNOWN → the view renders "—" (ADR §4),
 * not a fabricated "+0%".
 */

import { describe, expect, it, beforeEach } from "vitest";
import { InMemoryEngineDb } from "@/lib/adapters/engine/db/in_memory_engine_db";
import { buildBrowserEngineAdapters } from "@/lib/composition_engine_browser";
import type { EnginePortBag } from "@/lib/composition_engine";
import { loadSummary } from "./use_summary";
import type { Skill, SkillState, QuizSession } from "@/lib/wire/engine_entities";

const SUBJECT = "act-english";
const LEARNER = "maya";
const NOW = "2026-07-01T12:00:00.000Z";

function skill(over: Partial<Skill> = {}): Skill {
  return {
    id: "s-punc",
    subject: SUBJECT,
    key: "punctuation",
    name: "Punctuation",
    share_of_test_pct: 20,
    accent_var: "--color-bucket-punctuation",
    description: "…",
    order: 1,
    ...over,
  };
}

function skillState(over: Partial<SkillState> = {}): SkillState {
  return {
    subject: SUBJECT,
    skill_id: "s-punc",
    learner_id: LEARNER,
    mastery: 0.5,
    last_seen: "2026-06-25T00:00:00.000Z",
    fsrs_stability: 3,
    fsrs_difficulty: 5,
    due_at: "2026-06-20T00:00:00.000Z", // due (past) so it is the weakest+due pick
    fsrs_card: null,
    ...over,
  };
}

let db: InMemoryEngineDb;
let ports: EnginePortBag;

beforeEach(() => {
  db = new InMemoryEngineDb();
  db.seedSkills([skill(), skill({ id: "s-gram", key: "grammar", name: "Grammar", order: 2 })]);
  ports = buildBrowserEngineAdapters({ engineDb: db });
});

async function openClosedSession(over: Partial<QuizSession> = {}): Promise<QuizSession> {
  const s = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
  return ports.sessionRepo.close(s.id, { score_correct: 7, score_total: 10 });
}

describe("loadSummary — absent start-snapshot (edge path first, ADR §4)", () => {
  it("unknown start mastery → delta UNKNOWN so the view renders '—'", async () => {
    db.seedSkillStates([skillState({ skill_id: "s-punc", mastery: 0.6 })]);
    const session = await openClosedSession();
    const vm = await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map(), // brand-new learner: nothing captured at open
      nowISO: NOW,
    });
    expect(vm.masteryDeltaKnown).toBe(false);
  });
});

describe("loadSummary — stored score, never recomputed (FR-G1)", () => {
  it("score tile reads the STORED score even if attempts disagree", async () => {
    db.seedSkillStates([skillState()]);
    const session = await openClosedSession();
    const vm = await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map([["s-punc", skillState({ mastery: 0.5 })]]),
      nowISO: NOW,
    });
    expect(vm.summary.scoreTile).toBe("7/10");
    expect(vm.summary.scoreCorrect).toBe(7);
    expect(vm.summary.scoreTotal).toBe(10);
  });

  it("throws when the session id is unknown (a seam defect, surfaced)", async () => {
    await expect(
      loadSummary(ports, {
        subject: SUBJECT,
        learnerId: LEARNER,
        sessionId: "does-not-exist",
        skillStateAtStart: new Map(),
        nowISO: NOW,
      }),
    ).rejects.toThrow(/session/i);
  });
});

describe("loadSummary — signed mastery delta from the snapshot (FR-G1, ADR §4)", () => {
  it("current − start for the focus skill, ×100, signed", async () => {
    // Start mastery 0.50; fresh read 0.62 → +12%.
    db.seedSkillStates([skillState({ skill_id: "s-punc", mastery: 0.62 })]);
    const session = await openClosedSession();
    const vm = await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map([["s-punc", skillState({ skill_id: "s-punc", mastery: 0.5 })]]),
      nowISO: NOW,
    });
    expect(vm.masteryDeltaKnown).toBe(true);
    expect(vm.summary.masteryDeltaTile).toBe("+12%");
  });

  it("a mastery drop keeps its sign", async () => {
    db.seedSkillStates([skillState({ skill_id: "s-punc", mastery: 0.47 })]);
    const session = await openClosedSession();
    const vm = await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map([["s-punc", skillState({ skill_id: "s-punc", mastery: 0.5 })]]),
      nowISO: NOW,
    });
    expect(vm.summary.masteryDeltaTile).toBe("-3%");
  });
});

describe("loadSummary — recommended next re-opens Quiz on the weakest+due skill (FR-G1/G2)", () => {
  it("names the weakest+due skill and a drill mode", async () => {
    // s-punc is due+weaker; s-gram not due.
    db.seedSkillStates([
      skillState({ skill_id: "s-punc", mastery: 0.4, due_at: "2026-06-20T00:00:00.000Z" }),
      skillState({ skill_id: "s-gram", mastery: 0.9, due_at: "2026-08-01T00:00:00.000Z" }),
    ]);
    const session = await openClosedSession();
    const vm = await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map([["s-punc", skillState({ skill_id: "s-punc", mastery: 0.4 })]]),
      nowISO: NOW,
    });
    expect(vm.summary.recommended.skillId).toBe("s-punc");
    expect(vm.summary.recommended.skillName).toBe("Punctuation");
    expect(vm.summary.recommended.mode).toBe("drill");
  });
});

describe("loadSummary — read-only (FR-A2): renders without writing skill_state", () => {
  it("creates no new skill_state rows for a learner with none seeded", async () => {
    const session = await openClosedSession();
    await loadSummary(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      sessionId: session.id,
      skillStateAtStart: new Map(),
      nowISO: NOW,
    });
    const rows = await ports.learnerRead.listSkillState(SUBJECT, LEARNER);
    expect(rows).toHaveLength(0);
  });
});
