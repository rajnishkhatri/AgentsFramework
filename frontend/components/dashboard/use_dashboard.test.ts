/**
 * Phase 1.2 — Dashboard orchestration (FR-C1..C5, L1 deterministic, TAP-1).
 *
 * Per F-R1 the Dashboard component owns NO domain logic: gathering the six
 * bucket cards (skillTaxonomy + learnerRead), picking today's weakest+due focus,
 * and counting review-misses all live here, in the React-free `loadDashboard` /
 * `pickFocusSkillId` orchestration exercised in node against a seeded
 * InMemoryEngineDb — the analogue of openQuizItem/runQuizSubmit in use_quiz.ts.
 *
 * READ-ONLY invariant (FR-A2): the dashboard is a *view*; rendering it must NOT
 * write skill_state. It therefore reads via learnerRead.listSkillState and does
 * NOT call scheduler.next() (which seeds/writes for a new learner). The
 * "no-write" test below is the failure-first guard.
 */

import { describe, expect, it, beforeEach } from "vitest";
import { InMemoryEngineDb } from "@/lib/adapters/engine/db/in_memory_engine_db";
import { buildBrowserEngineAdapters } from "@/lib/composition_engine_browser";
import type { EnginePortBag } from "@/lib/composition_engine";
import { loadDashboard } from "./use_dashboard";
import { DEV_LEARNER_ID } from "@/lib/adapters/engine/_dev_seed";
import type { Question, Skill, SkillState } from "@/lib/wire/engine_entities";

const SUBJECT = "act-english";
// The browser composition auto-seeds the dev corpus under DEV_LEARNER_ID
// (buildBrowserEngineAdapters → seedDevCorpus). Bind LEARNER to that id so the
// hand-seeded rows and the auto-seeded rows land on the same learner — keeps the
// miss-count arithmetic deterministic and independent of the dev learner's name.
const LEARNER = DEV_LEARNER_ID;
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

function state(over: Partial<SkillState> = {}): SkillState {
  return {
    subject: SUBJECT,
    skill_id: "s-punc",
    learner_id: LEARNER,
    mastery: 0.5,
    last_seen: null,
    fsrs_stability: 1,
    fsrs_difficulty: 5,
    due_at: NOW,
    fsrs_card: null,
    ...over,
  } as SkillState;
}

function question(over: Partial<Question> = {}): Question {
  return {
    id: "q-punc-1",
    subject: SUBJECT,
    skill_id: "s-punc",
    difficulty: 3,
    context_html: "The committee <u>have</u> decided.",
    stem: "Which choice is best?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "has", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: { A: "…", B: "…" },
    why_correct_md: "…",
    why_tempted_md: "…",
    rule_md: "…",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

const SIX_SKILLS: Skill[] = [
  skill({ id: "s-punc", key: "punctuation", name: "Punctuation", order: 1 }),
  skill({ id: "s-gram", key: "grammar", name: "Grammar", order: 2 }),
  skill({ id: "s-sent", key: "sentence", name: "Sentence structure", order: 3 }),
  skill({ id: "s-rhet", key: "rhetoric", name: "Rhetoric", order: 4 }),
  skill({ id: "s-org", key: "organization", name: "Organization", order: 5 }),
  skill({ id: "s-style", key: "style", name: "Conciseness", order: 6 }),
];

let db: InMemoryEngineDb;
let ports: EnginePortBag;

beforeEach(() => {
  db = new InMemoryEngineDb();
  db.seedSkills(SIX_SKILLS);
  ports = buildBrowserEngineAdapters({ engineDb: db });
});

// pickFocusSkillId's own selection-rule table moved to
// lib/translators/focus_pick.test.ts when the helper was extracted to a shared
// translator (used by both this screen and the Summary recommended-next card).

describe("loadDashboard — READ-ONLY (FR-A2): rendering must not write skill_state", () => {
  it("does not seed/write skill_state for a brand-new learner", async () => {
    const before = await db.listSkillState(SUBJECT, LEARNER);
    expect(before).toEqual([]); // precondition: no rows

    await loadDashboard(ports, { subject: SUBJECT, learnerId: LEARNER, nowISO: NOW });

    const after = await db.listSkillState(SUBJECT, LEARNER);
    expect(after, "loadDashboard must not create skill_state rows").toEqual([]);
  });
});

describe("loadDashboard — FR-C3 six-bucket mastery grid", () => {
  it("returns exactly six bucket cards (one per skill), even for a new learner", async () => {
    const vm = await loadDashboard(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      nowISO: NOW,
    });
    expect(vm.buckets).toHaveLength(6);
    // A brand-new learner has no skill_state → every card is 0% and not-due.
    for (const b of vm.buckets) {
      expect(b.masteryPct).toBe(0);
      expect(b.due).toBe(false);
    }
  });

  it("maps real mastery + due onto the matching bucket cards", async () => {
    db.seedSkillStates([
      state({ skill_id: "s-punc", mastery: 0.42, due_at: NOW }), // due
      state({ skill_id: "s-gram", mastery: 0.9, due_at: "2999-01-01T00:00:00.000Z" }),
    ]);
    const vm = await loadDashboard(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      nowISO: NOW,
    });
    const punc = vm.buckets.find((b) => b.skillId === "s-punc")!;
    const gram = vm.buckets.find((b) => b.skillId === "s-gram")!;
    expect(punc.masteryPct).toBe(42);
    expect(punc.due).toBe(true);
    expect(gram.masteryPct).toBe(90);
    expect(gram.due).toBe(false);
  });
});

describe("loadDashboard — FR-C2 today's-focus banner", () => {
  it("is the weakest+due skill and carries a reviewed question + Quiz CTA", async () => {
    db.seedSkillStates([
      state({ skill_id: "s-punc", mastery: 0.3, due_at: NOW }),
      state({ skill_id: "s-gram", mastery: 0.7, due_at: NOW }),
    ]);
    db.seedQuestions([question({ id: "q-punc-1", skill_id: "s-punc" })]);
    const vm = await loadDashboard(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      nowISO: NOW,
    });
    expect(vm.todayFocus.present).toBe(true);
    if (vm.todayFocus.present) {
      expect(vm.todayFocus.skillId).toBe("s-punc");
      expect(vm.todayFocus.questionId).toBe("q-punc-1");
      expect(vm.todayFocus.ctaLabel).toBe("Start adaptive session");
    }
  });

  it("hides the banner (present:false) when the focus skill has no reviewed question", async () => {
    db.seedSkillStates([state({ skill_id: "s-punc", mastery: 0.3, due_at: NOW })]);
    // No questions seeded → no reviewed item to serve.
    const vm = await loadDashboard(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      nowISO: NOW,
    });
    expect(vm.todayFocus.present).toBe(false);
  });
});

describe("loadDashboard — FR-C5 review-my-misses count (empty-state first)", () => {
  it("is 0 for a learner with no misses (zero empty state)", async () => {
    const vm = await loadDashboard(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      nowISO: NOW,
    });
    expect(vm.reviewMissesCount).toBe(0);
  });

  it("counts the learner's incorrect attempts", async () => {
    db.seedSkillStates([state({ skill_id: "s-punc", mastery: 0.3, due_at: NOW })]);
    db.seedQuestions([question({ id: "q-punc-1", skill_id: "s-punc", answer_letter: "B" })]);
    const session = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    await ports.attemptRepo.record({
      subject: SUBJECT,
      session_id: session.id,
      question_id: "q-punc-1",
      chosen_letter: "A", // wrong (answer is B)
      correct: false,
      elapsed_ms: 1000,
      used_hint: false,
    });
    const vm = await loadDashboard(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      nowISO: NOW,
    });
    expect(vm.reviewMissesCount).toBe(1);
  });

  it("dedupes the same missed question (matches review pool size)", async () => {
    db.seedSkillStates([state({ skill_id: "s-punc", mastery: 0.3, due_at: NOW })]);
    db.seedQuestions([
      question({ id: "q-a", skill_id: "s-punc", answer_letter: "B" }),
      question({ id: "q-b", skill_id: "s-punc", answer_letter: "B" }),
    ]);
    const session = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    for (const id of ["q-a", "q-b", "q-a", "q-a"]) {
      await ports.attemptRepo.record({
        subject: SUBJECT,
        session_id: session.id,
        question_id: id,
        chosen_letter: "A",
        correct: false,
        elapsed_ms: 1000,
        used_hint: false,
      });
    }
    const vm = await loadDashboard(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      nowISO: NOW,
    });
    // 4 incorrect attempts, 2 unique question ids → badge shows 2
    expect(vm.reviewMissesCount).toBe(2);
  });

  it("clears a miss from the badge after a later correct attempt", async () => {
    db.seedSkillStates([state({ skill_id: "s-punc", mastery: 0.3, due_at: NOW })]);
    db.seedQuestions([
      question({ id: "q-a", skill_id: "s-punc", answer_letter: "B" }),
      question({ id: "q-b", skill_id: "s-punc", answer_letter: "B" }),
    ]);
    const prior = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    for (const id of ["q-a", "q-b"]) {
      await ports.attemptRepo.record({
        subject: SUBJECT,
        session_id: prior.id,
        question_id: id,
        chosen_letter: "A",
        correct: false,
        elapsed_ms: 1000,
        used_hint: false,
      });
    }
    const before = await loadDashboard(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      nowISO: NOW,
    });
    expect(before.reviewMissesCount).toBe(2);

    const review = await ports.sessionRepo.open(SUBJECT, LEARNER, "review");
    await ports.attemptRepo.record({
      subject: SUBJECT,
      session_id: review.id,
      question_id: "q-a",
      chosen_letter: "B",
      correct: true,
      elapsed_ms: 1000,
      used_hint: false,
    });
    await ports.attemptRepo.record({
      subject: SUBJECT,
      session_id: review.id,
      question_id: "q-b",
      chosen_letter: "A",
      correct: false,
      elapsed_ms: 1000,
      used_hint: false,
    });
    const after = await loadDashboard(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      nowISO: NOW,
    });
    expect(after.reviewMissesCount).toBe(1);
  });
});

describe("loadDashboard — C1 rail + greeting (FR-1/FR-2/FR-15)", () => {
  it("rail_unavailable_on_listByLearner_reject", async () => {
    const rejecting = {
      ...ports,
      sessionRepo: {
        ...ports.sessionRepo,
        listByLearner: async () => {
          throw new Error("ECONNRESET");
        },
      },
    };
    const vm = await loadDashboard(rejecting, {
      subject: SUBJECT,
      learnerId: LEARNER,
      displayName: "Garvit",
      nowISO: NOW,
    });
    expect(vm.greeting.headline).toMatch(/Garvit/);
    expect(vm.buckets.length).toBeGreaterThan(0);
    expect(vm.rail.status).toBe("unavailable");
    expect(vm.rail.weekly.label).toBe("—");
  });

  it("rail_read_fires_concurrently", async () => {
    const started: string[] = [];
    const release: Array<() => void> = [];
    const gate = () =>
      new Promise<void>((resolve) => {
        release.push(resolve);
      });

    const slow = {
      ...ports,
      skillTaxonomy: {
        ...ports.skillTaxonomy,
        list: async (subject: string) => {
          started.push("skills");
          await gate();
          return ports.skillTaxonomy.list(subject);
        },
      },
      learnerRead: {
        ...ports.learnerRead,
        listSkillState: async (subject: string, learnerId: string) => {
          started.push("states");
          await gate();
          return ports.learnerRead.listSkillState(subject, learnerId);
        },
      },
      attemptRepo: {
        ...ports.attemptRepo,
        misses: async (subject: string, learnerId: string) => {
          started.push("misses");
          await gate();
          return ports.attemptRepo.misses(subject, learnerId);
        },
      },
      sessionRepo: {
        ...ports.sessionRepo,
        listByLearner: async (
          subject: string,
          learnerId: string,
          options?: { sinceISO?: string },
        ) => {
          started.push("rail");
          await gate();
          return ports.sessionRepo.listByLearner(subject, learnerId, options);
        },
      },
      questionRepo: {
        ...ports.questionRepo,
        nextReviewed: async (subject: string, skillId: string) => {
          started.push("focus_question");
          await gate();
          return ports.questionRepo.nextReviewed(subject, skillId);
        },
      },
    };

    // Seed a due skill so the speculative focus prefetch has a target.
    db.seedSkillStates([state({ skill_id: "s-punc", mastery: 0.3, due_at: NOW })]);
    db.seedQuestions([question({ id: "q-punc-1", skill_id: "s-punc" })]);

    const pending = loadDashboard(slow, {
      subject: SUBJECT,
      learnerId: LEARNER,
      nowISO: NOW,
    });
    // All five must have started before any resolve (single Promise.all).
    await new Promise((r) => setTimeout(r, 10));
    expect(started.sort()).toEqual([
      "focus_question",
      "misses",
      "rail",
      "skills",
      "states",
    ]);
    for (const r of release) r();
    await pending;
  });

  it("cold_start_returns_zero_and_present_false", async () => {
    const vm = await loadDashboard(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      nowISO: NOW,
    });
    expect(vm.rail.status).toBe("ok");
    expect(vm.rail.streak.present).toBe(false);
    expect(vm.rail.streak.days).toBe(0);
    expect(vm.rail.weekly.count).toBe(0);
    expect(vm.rail.weekly.label).toBe("0 / 3 sessions");
  });

  // FR-2: production path must not read window.__PREACT_E2E_* (composition
  // root owns the fail-once seam).
  it("does_not_reference_e2e_globals", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const src = fs.readFileSync(
      path.join(__dirname, "use_dashboard.ts"),
      "utf8",
    );
    expect(src).not.toContain("__PREACT_E2E_");
  });

  // FR-6: rail result is a discriminated union — no `as QuizSession[]` cast.
  it("rail_result_is_discriminated_union_not_sentinel", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const src = fs.readFileSync(
      path.join(__dirname, "use_dashboard.ts"),
      "utf8",
    );
    expect(src).not.toMatch(/as\s+QuizSession\[\]/);
    expect(src).not.toContain("RAIL_UNAVAILABLE");
    expect(src).toMatch(/type\s+RailResult\s*=/);
  });
});
