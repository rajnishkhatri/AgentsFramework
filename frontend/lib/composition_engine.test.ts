/**
 * Tests for the engine composition root (ADR-0006).
 *
 * Asserts the seam selection (DATABASE_URL → live pg seam; absent → in-memory)
 * and that the wired bag exposes all eight ports (7 ADR-0006 + LearnerReadRepo,
 * ADR-0011), end-to-end over a seeded in-memory db (open → grade → record →
 * review → close, the FR-D1..D6 loop).
 */

import { describe, expect, it } from "vitest";
import {
  buildEngineAdapters,
  selectEngineDb,
} from "./composition_engine";
import { InMemoryEngineDb } from "./adapters/engine/db/in_memory_engine_db";
import type { Question, Skill } from "./wire/engine_entities";

describe("selectEngineDb — seam selection", () => {
  it("falls back to InMemoryEngineDb without DATABASE_URL", () => {
    expect(selectEngineDb({})).toBeInstanceOf(InMemoryEngineDb);
    expect(selectEngineDb({ DATABASE_URL: "" })).toBeInstanceOf(InMemoryEngineDb);
    expect(selectEngineDb({ DATABASE_URL: "   " })).toBeInstanceOf(InMemoryEngineDb);
  });

  it("builds the live pg seam when DATABASE_URL is set (lazy — no connection)", () => {
    // pgEngineDb constructs the pool lazily; this asserts SELECTION, not I/O.
    const db = selectEngineDb({
      DATABASE_URL: "postgresql://u:p@localhost:5432/db",
    });
    expect(db).not.toBeInstanceOf(InMemoryEngineDb);
  });
});

describe("buildEngineAdapters — full bag + end-to-end loop", () => {
  it("exposes all eight ports (7 ADR-0006 + LearnerReadRepo, ADR-0011)", () => {
    const bag = buildEngineAdapters({ env: {} });
    expect(bag.skillTaxonomy).toBeDefined();
    expect(bag.questionRepo).toBeDefined();
    expect(bag.attemptRepo).toBeDefined();
    expect(bag.sessionRepo).toBeDefined();
    expect(bag.scheduler).toBeDefined();
    expect(bag.grader).toBeDefined();
    expect(bag.contentRepo).toBeDefined();
    // ADR-0011: the read-only skill_state view must be wired too (Dashboard
    // mastery FR-C3 + Summary delta FR-G1). A subset assertion above would
    // typecheck without it, so name it explicitly.
    expect(bag.learnerRead).toBeDefined();
  });

  it("runs the open→grade→record→review→close loop through the wired ports", async () => {
    const db = new InMemoryEngineDb();
    const skill: Skill = {
      id: "s1",
      subject: "act-english",
      key: "punctuation",
      name: "Punctuation",
      share_of_test_pct: 13,
      accent_var: "",
      description: "",
      order: 1,
    };
    const q: Question = {
      id: "q1",
      subject: "act-english",
      skill_id: "s1",
      difficulty: 2,
      context_html: "",
      stem: "",
      choices: [
        { letter: "A", label: "NO CHANGE", is_no_change: true },
        { letter: "B", label: "has", is_no_change: false },
      ],
      answer_letter: "B",
      per_choice_rationale: { A: "tempted", B: "correct" },
      why_correct_md: "",
      why_tempted_md: "",
      rule_md: "",
      item_type: "underlined-span-mc",
      misconception: null,
      reviewed: true,
      generated_by: "test",
    };
    db.seedSkills([skill]);
    db.seedQuestions([q]);

    const bag = buildEngineAdapters({ env: {}, engineDb: db });

    // Scheduler seeds + picks (FR-A7/A1).
    const pick = await bag.scheduler.next("act-english", "alice");
    expect(pick.question_id).toBe("q1");

    // Open a session (FR-D1).
    const session = await bag.sessionRepo.open("act-english", "alice", "adaptive");

    // Grade a wrong pick (FR-C3): two rationale handles.
    const verdict = bag.grader.grade(q, { letter: "A" });
    expect(verdict).not.toBeNull();
    expect(verdict!.correct).toBe(false);
    expect(verdict!.rationale_key).toBe("A");
    expect(verdict!.correct_letter).toBe("B");

    // Record the attempt (FR-D2).
    const attempt = await bag.attemptRepo.record({
      subject: "act-english",
      session_id: session.id,
      question_id: q.id,
      chosen_letter: "A",
      correct: verdict!.correct,
      elapsed_ms: 1500,
      used_hint: false,
    });

    // Scheduler review writes skill_state (FR-A2).
    const state = await bag.scheduler.review(attempt);
    expect(state.learner_id).toBe("alice");

    // It shows up in misses (FR-D4).
    const misses = await bag.attemptRepo.misses("act-english", "alice");
    expect(misses.map((m) => m.id)).toContain(attempt.id);

    // Close stores the tally (FR-D3).
    const closed = await bag.sessionRepo.close(session.id, {
      score_correct: 0,
      score_total: 1,
    });
    expect(closed.ended_at).not.toBeNull();
    expect(closed.score_total).toBe(1);
  });
});
