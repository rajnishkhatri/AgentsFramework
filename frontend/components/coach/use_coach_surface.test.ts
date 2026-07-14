/**
 * Sprint B1 — countMissesOnSkill (FR-1, FR-6; red-first).
 *
 * Skill-scoped history for coach chrome: AttemptRepo.misses + QuestionRepo.get
 * join (Attempt has no skill_id). Errors / missing skillId → null (honest absent).
 */

import { beforeEach, describe, expect, it } from "vitest";
import { InMemoryEngineDb } from "@/lib/adapters/engine/db/in_memory_engine_db";
import { buildBrowserEngineAdapters } from "@/lib/composition_engine_browser";
import type { EnginePortBag } from "@/lib/composition_engine";
import type { Question } from "@/lib/wire/engine_entities";
import { countMissesOnSkill, skillNameById } from "./use_coach_surface";
import { DEV_LEARNER_ID } from "@/lib/adapters/engine/_dev_seed";
import type { Skill } from "@/lib/wire/engine_entities";

const SUBJECT = "act-english";
const LEARNER = DEV_LEARNER_ID;

function skill(over: Partial<Skill> = {}): Skill {
  return {
    id: "s-punc",
    subject: SUBJECT,
    key: "punctuation",
    name: "Punctuation",
    share_of_test_pct: 20,
    accent_var: "--color-bucket-punctuation",
    description: "Commas, semicolons.",
    order: 1,
    ...over,
  };
}

function question(over: Partial<Question> = {}): Question {
  return {
    id: "q-punc-1",
    subject: SUBJECT,
    skill_id: "s-punc",
    difficulty: 3,
    context_html: "…",
    stem: "Which?",
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

let db: InMemoryEngineDb;
let ports: EnginePortBag;

beforeEach(() => {
  db = new InMemoryEngineDb();
  ports = buildBrowserEngineAdapters({ engineDb: db });
});

describe("countMissesOnSkill — honest absent (FR-1)", () => {
  it("returns null when skillId is omitted", async () => {
    const n = await countMissesOnSkill(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
    });
    expect(n).toBeNull();
  });

  it("returns null when misses load throws", async () => {
    const broken: EnginePortBag = {
      ...ports,
      attemptRepo: {
        ...ports.attemptRepo,
        misses: async () => {
          throw new Error("db down");
        },
      },
    };
    const n = await countMissesOnSkill(broken, {
      subject: SUBJECT,
      learnerId: LEARNER,
      skillId: "s-punc",
    });
    expect(n).toBeNull();
  });
});

describe("countMissesOnSkill — skill-scoped count (FR-6)", () => {
  it("counts unique miss question_ids on the pinned skill only", async () => {
    db.seedQuestions([
      question({ id: "q1", skill_id: "s-punc" }),
      question({ id: "q2", skill_id: "s-punc", stem: "other" }),
      question({ id: "q3", skill_id: "s-gram", stem: "grammar" }),
    ]);
    const session = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    for (const qid of ["q1", "q1", "q2", "q3"]) {
      await ports.attemptRepo.record({
        subject: SUBJECT,
        session_id: session.id,
        question_id: qid,
        chosen_letter: "A",
        correct: false,
        elapsed_ms: 1000,
        used_hint: false,
      });
    }

    const n = await countMissesOnSkill(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      skillId: "s-punc",
    });
    expect(n).toBe(2);
  });

  it("returns 0 when there are misses but none on the skill", async () => {
    db.seedQuestions([
      question({ id: "q3", skill_id: "s-gram", stem: "grammar" }),
    ]);
    const session = await ports.sessionRepo.open(SUBJECT, LEARNER, "adaptive");
    await ports.attemptRepo.record({
      subject: SUBJECT,
      session_id: session.id,
      question_id: "q3",
      chosen_letter: "A",
      correct: false,
      elapsed_ms: 1000,
      used_hint: false,
    });
    const n = await countMissesOnSkill(ports, {
      subject: SUBJECT,
      learnerId: LEARNER,
      skillId: "s-punc",
    });
    expect(n).toBe(0);
  });
});

describe("skillNameById — C-3 friendly label, honest absent", () => {
  it("resolves a pinned skillId to its display name", async () => {
    db.seedSkills([
      skill({ id: "s-punc", name: "Punctuation" }),
      skill({ id: "s-gram", key: "grammar", name: "Grammar & Usage" }),
    ]);
    const name = await skillNameById(ports, SUBJECT, "s-gram");
    expect(name).toBe("Grammar & Usage");
  });

  it("returns null for an unknown skillId (never echoes the raw id)", async () => {
    db.seedSkills([skill({ id: "s-punc", name: "Punctuation" })]);
    const name = await skillNameById(ports, SUBJECT, "s-does-not-exist");
    expect(name).toBeNull();
  });

  it("returns null when skillId is null/empty (no honest scope)", async () => {
    expect(await skillNameById(ports, SUBJECT, null)).toBeNull();
    expect(await skillNameById(ports, SUBJECT, "")).toBeNull();
  });

  it("returns null when the taxonomy read throws (honest absent)", async () => {
    const broken: EnginePortBag = {
      ...ports,
      skillTaxonomy: {
        ...ports.skillTaxonomy,
        list: async () => {
          throw new Error("db down");
        },
      },
    };
    expect(await skillNameById(broken, SUBJECT, "s-punc")).toBeNull();
  });
});
