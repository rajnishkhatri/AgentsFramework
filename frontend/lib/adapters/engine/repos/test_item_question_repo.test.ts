/**
 * L1/L2 contract for TestItemQuestionRepo (ADR-0021, spec FR-B5/B6/C4).
 *
 * Failure paths FIRST (TAP-4): the reviewed gate under a REGRESSED upstream
 * repo (defense in depth — the adapter must filter even if TestItemRepo lies),
 * and the read-only posture (save() throws), before the mapping happy path.
 */

import { describe, expect, it } from "vitest";
import type { TestItemRepo } from "../../../ports/engine/test_item_repo";
import { EngineRepoError } from "../../../ports/engine/errors";
import type { Question, TestItem } from "../../../wire/engine_entities";
import { TestItemQuestionRepo } from "./test_item_question_repo";

function bankItem(over: Partial<TestItem> = {}): TestItem {
  return {
    id: "ti-gen-aaaa000011112222",
    subject: "act-english",
    skill_id: "s-gram",
    difficulty: 3,
    context_html: "The results were consistent <u>to</u> the hypothesis.",
    stem_md: "Which choice completes the idiom correctly?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "with", is_no_change: false },
      { letter: "C", label: "for", is_no_change: false },
      { letter: "D", label: "about", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: {
      A: "'Consistent to' is not idiomatic.",
      B: "'Consistent with' is the idiom.",
      C: "'Consistent for' is not idiomatic.",
      D: "'Consistent about' means something else.",
    },
    why_correct_md: "Idioms are fixed pairings.",
    why_tempted_md: "'To' feels connective.",
    rule_md: "Learn preposition pairings as units.",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "gpt-4o-mini@run-1",
    ...over,
  };
}

/** A records-and-answers fake of the TestItemRepo PORT. */
function fakeRepo(rows: TestItem[]): TestItemRepo {
  return {
    async listReviewed(subject: string): Promise<TestItem[]> {
      // NOTE: deliberately NO reviewed filter — test doubles below use this to
      // simulate a regressed upstream seam (FR-B5 defense in depth).
      return rows.filter((r) => r.subject === subject);
    },
  };
}

describe("TestItemQuestionRepo — failure paths first", () => {
  it("never returns an unreviewed row even if the upstream repo regresses (FR-B5)", async () => {
    const lying = fakeRepo([
      bankItem({ id: "ti-bad", reviewed: false }),
      bankItem({ id: "ti-good", reviewed: true }),
    ]);
    const repo = new TestItemQuestionRepo(lying, "act-english");
    const q = await repo.nextReviewed("act-english", "s-gram");
    expect(q?.id).toBe("ti-good");
    expect(await repo.get("ti-bad")).toBeNull();
  });

  it("save() throws — serving code never writes the bank (read-only posture)", async () => {
    const repo = new TestItemQuestionRepo(fakeRepo([]), "act-english");
    await expect(
      repo.save({ id: "q-x" } as unknown as Question),
    ).rejects.toBeInstanceOf(EngineRepoError);
  });

  it("nextReviewed returns null (not throw) when the skill has no bank item (FR-B4 support)", async () => {
    const repo = new TestItemQuestionRepo(fakeRepo([bankItem()]), "act-english");
    expect(await repo.nextReviewed("act-english", "s-punc")).toBeNull();
  });

  it("get returns null for an unknown id", async () => {
    const repo = new TestItemQuestionRepo(fakeRepo([bankItem()]), "act-english");
    expect(await repo.get("nope")).toBeNull();
  });
});

describe("TestItemQuestionRepo — lossless mapping (FR-C4) + scheduling (FR-B6)", () => {
  it("maps every Question field from a real bank column — nothing synthesized", async () => {
    const item = bankItem();
    const repo = new TestItemQuestionRepo(fakeRepo([item]), "act-english");
    const q = await repo.nextReviewed("act-english", "s-gram");
    expect(q).toEqual({
      id: item.id,
      subject: item.subject,
      skill_id: item.skill_id,
      difficulty: item.difficulty,
      context_html: item.context_html,
      stem: item.stem_md, // stem_md ↔ Question.stem (documented mapping)
      choices: item.choices,
      answer_letter: item.answer_letter,
      per_choice_rationale: item.per_choice_rationale,
      why_correct_md: item.why_correct_md,
      why_tempted_md: item.why_tempted_md,
      rule_md: item.rule_md,
      item_type: item.item_type,
      reviewed: true,
      generated_by: item.generated_by,
    });
  });

  it("get(bankId) resolves for scheduler.review() on a bank attempt (FR-B6)", async () => {
    const item = bankItem();
    const repo = new TestItemQuestionRepo(fakeRepo([item]), "act-english");
    const q = await repo.get(item.id);
    expect(q?.skill_id).toBe("s-gram");
  });

  it("nextReviewed picks deterministically: lowest difficulty, then id", async () => {
    const repo = new TestItemQuestionRepo(
      fakeRepo([
        bankItem({ id: "ti-b-hard", difficulty: 4 }),
        bankItem({ id: "ti-z-easy", difficulty: 2 }),
        bankItem({ id: "ti-a-easy", difficulty: 2 }),
      ]),
      "act-english",
    );
    const q = await repo.nextReviewed("act-english", "s-gram");
    expect(q?.id).toBe("ti-a-easy");
  });
});
