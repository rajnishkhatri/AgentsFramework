/**
 * S-D1 — exam home loader (FR-10–12).
 * Status per section; in_progress blocks a second start.
 */

import { describe, expect, it } from "vitest";
import { ExactLetterGrader } from "@/lib/adapters/engine/grader/exact_letter_grader";
import { InMemoryEngineDb } from "@/lib/adapters/engine/db/in_memory_engine_db";
import { DrizzleExamRunRepo } from "@/lib/adapters/engine/repos/drizzle_exam_run_repo";
import { EngineRepoError } from "@/lib/ports/engine/errors";
import type { ExamForm, ExamQuestion } from "@/lib/wire/exam_entities";
import { loadExamHome, startExamSection } from "./use_exam_home";

const LEARNER = "learner-1";
const NOW = new Date("2026-09-02T12:00:00.000Z");

function question(over: Partial<ExamQuestion> = {}): ExamQuestion {
  return {
    id: "q-1",
    subject: "act-english",
    skill_id: "s-punct",
    difficulty: 2,
    context_html: "x",
    stem: "y",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "b", is_no_change: false },
    ],
    answer_letter: "A",
    per_choice_rationale: {},
    why_correct_md: "",
    why_tempted_md: "",
    rule_md: "",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "test",
    reporting_category: null,
    scored: true,
    passage: null,
    ...over,
  };
}

function form(): ExamForm {
  return {
    id: "two-section",
    title: "Two section",
    blueprint: "test01",
    composite_sections: ["english"],
    sections: [
      {
        code: "english",
        title: "English",
        minutes: 10,
        choice_count: 4,
        directions: "English directions",
        composite: true,
        scale_table: null,
        questions: [question()],
      },
      {
        code: "math",
        title: "Math",
        minutes: 15,
        choice_count: 4,
        directions: "Math directions",
        composite: false,
        scale_table: null,
        questions: [question({ id: "q-math" })],
      },
    ],
  };
}

function harness() {
  const db = new InMemoryEngineDb();
  const f = form();
  const repo = new DrizzleExamRunRepo({
    db,
    grader: new ExactLetterGrader(),
    getForm: () => f,
    newId: () => "run-1",
    now: () => NOW,
  });
  return { repo, forms: [f] };
}

describe("exam_home (FR-10–12)", () => {
  it("lists forms with not_started status per section when the learner has no run", async () => {
    const { repo, forms } = harness();
    const vm = await loadExamHome(repo, {
      learnerId: LEARNER,
      forms,
      now: NOW,
    });
    expect(vm.forms).toHaveLength(1);
    expect(vm.forms[0]?.formId).toBe("two-section");
    expect(vm.forms[0]?.title).toBe("Two section");
    expect(vm.forms[0]?.runId).toBeNull();
    expect(vm.forms[0]?.sections.map((s) => s.status)).toEqual([
      "not_started",
      "not_started",
    ]);
    expect(vm.forms[0]?.sections[0]?.recommended).toBe(true);
    expect(vm.forms[0]?.sections[1]?.recommended).toBe(false);
    expect(vm.forms[0]?.sections.every((s) => s.startBlocked === false)).toBe(
      true,
    );
  });

  it("shows in_progress remaining time and blocks a second start (FR-10/FR-12)", async () => {
    const { repo, forms } = harness();
    const started = await startExamSection(repo, {
      learnerId: LEARNER,
      forms,
      formId: "two-section",
      sectionCode: "english",
    });
    expect(started.runId).toBe("run-1");
    await repo.beginSection({
      learnerId: LEARNER,
      runId: started.runId,
      sectionCode: "english",
    });

    const vm = await loadExamHome(repo, {
      learnerId: LEARNER,
      forms,
      now: NOW,
    });
    const english = vm.forms[0]?.sections.find((s) => s.code === "english");
    const math = vm.forms[0]?.sections.find((s) => s.code === "math");
    expect(english?.status).toBe("in_progress");
    expect(english?.remainingMs).toBe(10 * 60_000);
    expect(english?.startBlocked).toBe(false);
    expect(math?.status).toBe("not_started");
    expect(math?.startBlocked).toBe(true);

    await expect(
      startExamSection(repo, {
        learnerId: LEARNER,
        forms,
        formId: "two-section",
        sectionCode: "math",
      }),
    ).rejects.toBeInstanceOf(EngineRepoError);
  });
});
