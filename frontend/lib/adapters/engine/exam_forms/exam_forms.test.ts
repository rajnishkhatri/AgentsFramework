/**
 * FR-6 — exam form registry load-time asserts.
 * Empty form / empty section / unsupported choice_count must throw at load,
 * never render a blank timed section.
 */

import { describe, expect, it } from "vitest";
import {
  SUPPORTED_CHOICE_COUNTS,
  assertExamFormLoadable,
  getExamForm,
  listExamForms,
  listRegisteredExamFormIds,
  loadAssetServedForm,
} from "./index";
import type { ExamForm } from "@/lib/wire/exam_entities";

function baseForm(over: Partial<ExamForm> = {}): ExamForm {
  return {
    id: "probe",
    title: "Probe",
    blueprint: "test01",
    composite_sections: ["english"],
    delivery: "client-bundled",
    sections: [
      {
        code: "english",
        title: "English",
        minutes: 18,
        choice_count: 4,
        directions: "Begin.",
        composite: true,
        scale_table: null,
        passages: [],
        questions: [
          {
            id: "q-1",
            subject: "act-english",
            skill_id: "s-gram",
            difficulty: 3,
            context_html: "<p>x</p>",
            stem: "stem",
            choices: [
              { letter: "A", label: "A", is_no_change: false },
              { letter: "B", label: "B", is_no_change: false },
              { letter: "C", label: "C", is_no_change: false },
              { letter: "D", label: "D", is_no_change: false },
            ],
            answer_letter: "B",
            per_choice_rationale: { A: "a", B: "b", C: "c", D: "d" },
            why_correct_md: "w",
            why_tempted_md: "t",
            rule_md: "r",
            item_type: "mc",
            reviewed: true,
            generated_by: "test",
            misconception: null,
            reporting_category: null,
            scored: true,
            passage: null,
            image: null,
          },
        ],
      },
    ],
    ...over,
  };
}

describe("exam_forms load-time asserts (FR-6)", () => {
  it("throws on an empty form (no sections)", () => {
    expect(() => assertExamFormLoadable(baseForm({ sections: [] }))).toThrow(
      /empty form/i,
    );
  });

  it("throws on an empty section (no questions)", () => {
    const form = baseForm();
    form.sections[0] = { ...form.sections[0]!, questions: [] };
    expect(() => assertExamFormLoadable(form)).toThrow(/empty section/i);
  });

  it("throws on unsupported choice_count (phase-1 renderer is 4 only)", () => {
    const form = baseForm();
    form.sections[0] = { ...form.sections[0]!, choice_count: 5 };
    expect(() => assertExamFormLoadable(form)).toThrow(/choice_count/i);
  });
});

describe("exam_forms registry", () => {
  it("exposes the Test-01 English form wrapping TEST01_SERVED_QUESTIONS", () => {
    const forms = listExamForms();
    expect(forms.length).toBeGreaterThan(0);
    const test01 = getExamForm("test01-english");
    expect(test01.sections[0]!.code).toBe("english");
    expect(test01.sections[0]!.questions.length).toBeGreaterThan(0);
    expect(test01.sections[0]!.choice_count).toBe(4);
  });
});

describe("exam_forms asset-served registry (B0-7 / FR-P2-19)", () => {
  it("registers an asset-served entry and does not list it when _generated is absent", () => {
    expect(listRegisteredExamFormIds()).toContain("fake-official-form");
    expect(loadAssetServedForm("fake-official-form")).toBeNull();
    expect(listExamForms().map((f) => f.id)).not.toContain("fake-official-form");
    expect(listExamForms().map((f) => f.id)).toContain("test01-english");
    expect(SUPPORTED_CHOICE_COUNTS).toEqual([4]);
  });
});
