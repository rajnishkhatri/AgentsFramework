/**
 * FR-B3 leak guard (ADR-0021 / ADR-0015 clause 1): the practice QuestionRepo
 * is STRUCTURALLY blind to the exam-item bank.
 *
 * The separation is by table (question vs test_item), not by a filter — so the
 * practice repo must never surface a bank row even when the bank holds a
 * reviewed item for the exact (subject, skill) being scheduled. This test
 * documents that property against the shared EngineDb fake; if a refactor ever
 * merged the stores, it fails.
 */

import { describe, expect, it } from "vitest";
import { InMemoryEngineDb } from "../db/in_memory_engine_db";
import { DrizzleQuestionRepo } from "./drizzle_question_repo";
import type { Question, TestItem } from "../../../wire/engine_entities";

const teaching = {
  context_html: "The team <u>were</u> ready.",
  per_choice_rationale: { A: "a…", B: "b…", C: "c…", D: "d…" },
  why_correct_md: "why",
  why_tempted_md: "tempted",
  rule_md: "rule",
  item_type: "underlined-span-mc",
} as const;

const choices = [
  { letter: "A", label: "NO CHANGE", is_no_change: true },
  { letter: "B", label: "was", is_no_change: false },
  { letter: "C", label: "have been", is_no_change: false },
  { letter: "D", label: "being", is_no_change: false },
];

function bankRow(): TestItem {
  return {
    id: "ti-gen-bank000000000001",
    subject: "act-english",
    skill_id: "s-gram",
    difficulty: 1, // deliberately the MOST attractive pick if it could leak
    stem_md: "Which choice is best?",
    choices,
    answer_letter: "B",
    reviewed: true,
    generated_by: "gpt-4o-mini@run-1",
    ...teaching,
  };
}

function questionRow(): Question {
  return {
    id: "q-practice-1",
    subject: "act-english",
    skill_id: "s-gram",
    difficulty: 3,
    stem: "Which choice is best?",
    choices,
    answer_letter: "B",
    reviewed: true,
    generated_by: "authored",
    ...teaching,
  };
}

describe("DrizzleQuestionRepo — blind to the exam-item bank (FR-B3)", () => {
  it("nextReviewed never returns a test_item row, even a reviewed easier one", async () => {
    const db = new InMemoryEngineDb();
    db.seedQuestions([questionRow()]);
    db.seedTestItems([bankRow()]); // same subject+skill, lower difficulty
    const repo = new DrizzleQuestionRepo(db);
    const next = await repo.nextReviewed("act-english", "s-gram");
    expect(next?.id).toBe("q-practice-1"); // never ti-gen-*
  });

  it("returns null (not a bank row) when only the bank covers the skill", async () => {
    const db = new InMemoryEngineDb();
    db.seedTestItems([bankRow()]);
    const repo = new DrizzleQuestionRepo(db);
    expect(await repo.nextReviewed("act-english", "s-gram")).toBeNull();
    expect(await repo.get("ti-gen-bank000000000001")).toBeNull();
  });
});
