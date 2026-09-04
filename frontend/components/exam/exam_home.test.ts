/**
 * S-D1 — exam home loader (FR-10–12).
 * Status per section; in_progress blocks a second start.
 */

import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
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
    image: null,
    ...over,
  };
}

function form(): ExamForm {
  return {
    id: "two-section",
    title: "Two section",
    blueprint: "test01",
    composite_sections: ["english"],
    delivery: "client-bundled",
    sections: [
      {
        code: "english",
        title: "English",
        minutes: 10,
        choice_count: 4,
        directions: "English directions",
        composite: true,
        scale_table: null,
        passages: [],
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
        passages: [],
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
      now: NOW,
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
        now: NOW,
      }),
    ).rejects.toBeInstanceOf(EngineRepoError);
  });

  it("surfaces an in_progress attempt whose deadline has passed as expired (not Resume) and stops it blocking other sections", async () => {
    const { repo, forms } = harness();
    const started = await startExamSection(repo, {
      learnerId: LEARNER,
      forms,
      formId: "two-section",
      sectionCode: "english",
      now: NOW,
    });
    await repo.beginSection({
      learnerId: LEARNER,
      runId: started.runId,
      sectionCode: "english",
    });

    // english deadline = NOW + 10 min (12:10Z); load the home 11 min later.
    const AFTER_DEADLINE = new Date("2026-09-02T12:11:00.000Z");
    const vm = await loadExamHome(repo, {
      learnerId: LEARNER,
      forms,
      now: AFTER_DEADLINE,
    });
    const english = vm.forms[0]?.sections.find((s) => s.code === "english");
    const math = vm.forms[0]?.sections.find((s) => s.code === "math");

    // Was "in_progress · 0 min left · Resume" — a dead end. Now effectively Expired → Review.
    expect(english?.status).toBe("expired");
    expect(english?.remainingMs).toBeNull();
    // An expired section no longer blocks starting another section.
    expect(english?.startBlocked).toBe(false);
    expect(math?.startBlocked).toBe(false);

    // …and starting the other section must not throw "another section is in progress".
    await expect(
      startExamSection(repo, {
        learnerId: LEARNER,
        forms,
        formId: "two-section",
        sectionCode: "math",
        now: AFTER_DEADLINE,
      }),
    ).resolves.toMatchObject({ sectionCode: "math" });
  });
});

const PT2_GENERATED_CLIENT = join(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "lib/adapters/engine/exam_forms/_generated/act-practice-test-2.client.ts",
);

describe("S-I2 exam home lists PT2 (FR-P2-19)", () => {
  // Local-only tier: PT2's ©ACT `_generated/` artifact is gitignored and absent
  // in CI, so this real-form assertion skips there and runs locally.
  it.skipIf(!existsSync(PT2_GENERATED_CLIENT))(
    "lists PT2 beside Test-01 with four section statuses via getExamFormForClient",
    async () => {
      await import("@/lib/adapters/engine/exam_forms/generated_official_form");
      const db = new InMemoryEngineDb();
      const repo = new DrizzleExamRunRepo({
        db,
        grader: new ExactLetterGrader(),
      });
      const forms = await repo.listClientForms({ learnerId: LEARNER });
      const vm = await loadExamHome(repo, {
        learnerId: LEARNER,
        forms,
        now: NOW,
      });
      const ids = vm.forms.map((f) => f.formId);
      expect(ids).toContain("test01-english");
      expect(ids).toContain("act-practice-test-2");
      const pt2 = vm.forms.find((f) => f.formId === "act-practice-test-2");
      expect(pt2).toBeDefined();
      expect(pt2!.sections).toHaveLength(4);
      expect(pt2!.sections.map((s) => s.code)).toEqual([
        "english",
        "math",
        "reading",
        "science",
      ]);
      expect(pt2!.sections.every((s) => s.status === "not_started")).toBe(true);

      const client = await repo.getClientForm({
        learnerId: LEARNER,
        formId: "act-practice-test-2",
      });
      expect(client).not.toBeNull();
      expect(client!.sections).toHaveLength(4);
      expect(JSON.stringify(client)).not.toContain('"answer_letter"');
    },
  );
});
