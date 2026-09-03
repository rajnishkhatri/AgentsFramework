/**
 * Synthetic, non-©ACT 4-section asset-served form (B0-6).
 * CI substrate — never sourced from docs/preact9secure/.
 */

import type {
  AssetRef,
  ExamForm,
  ExamPassage,
  ExamQuestion,
  ExamSection,
  ExamSectionCode,
} from "../../../../wire/exam_entities";
import { needsImage } from "../exam_image_rule";

export const FAKE_OFFICIAL_FORM_ID = "fake-official-form";

function asset(key: string): AssetRef {
  return { store: "form-image", form_id: FAKE_OFFICIAL_FORM_ID, key };
}

function choices(): ExamQuestion["choices"] {
  return [
    { letter: "A", label: "A", is_no_change: false },
    { letter: "B", label: "B", is_no_change: false },
    { letter: "C", label: "C", is_no_change: false },
    { letter: "D", label: "D", is_no_change: false },
  ];
}

function q(
  over: Partial<ExamQuestion> &
    Pick<ExamQuestion, "id"> & { text_fidelity?: "ok" | "math-notation" | "low" },
  passage?: { is_figure: boolean },
): ExamQuestion {
  const fidelity = over.text_fidelity ?? "ok";
  const image = needsImage({ text_fidelity: fidelity }, passage)
    ? (over.image ?? asset(`${over.id}.png`))
    : null;
  const rest = { ...over };
  delete rest.text_fidelity;
  return {
    subject: "act-english",
    skill_id: "s-gram",
    difficulty: 2,
    context_html: "<p>x</p>",
    stem: "synthetic stem",
    choices: choices(),
    answer_letter: "B",
    per_choice_rationale: { A: "a", B: "b", C: "c", D: "d" },
    why_correct_md: "synthetic",
    why_tempted_md: "synthetic",
    rule_md: "synthetic",
    item_type: "mc",
    misconception: null,
    reviewed: true,
    generated_by: "fixture",
    reporting_category: "conventions",
    scored: true,
    passage: null,
    image,
    ...rest,
  };
}

function section(
  code: ExamSectionCode,
  title: string,
  questions: ExamQuestion[],
  passages: ExamPassage[] = [],
  scale_table: ExamSection["scale_table"] = null,
): ExamSection {
  return {
    code,
    title,
    minutes: 10,
    choice_count: 4,
    directions: "Synthetic directions.",
    composite: code !== "science",
    scale_table,
    passages,
    questions,
  };
}

const MATH_IMAGE = asset("math/q-2.png");
const FIGURE_IMAGE = asset("science/p-figure.png");

const FIGURE_PASSAGE: ExamPassage = {
  label: "P1",
  title: "Figure 1",
  intro: "A synthetic figure passage.",
  text: null,
  image: FIGURE_IMAGE,
  question_numbers: [1, 2],
};

export const FAKE_OFFICIAL_FORM: ExamForm = {
  id: FAKE_OFFICIAL_FORM_ID,
  title: "Fake Official Form",
  blueprint: "act-enhanced",
  composite_sections: ["english", "math", "reading"],
  delivery: "asset-served",
  sections: [
    section("english", "English", [
      q({ id: "e-1", text_fidelity: "ok" }),
      q({ id: "e-2", text_fidelity: "ok", scored: false }),
    ]),
    section(
      "math",
      "Math",
      [
        q({ id: "m-1", subject: "act-math", text_fidelity: "ok" }),
        q({
          id: "m-2",
          subject: "act-math",
          text_fidelity: "math-notation",
          image: MATH_IMAGE,
        }),
      ],
      [],
      { "0": 1, "1": 8, "2": 16 },
    ),
    section("reading", "Reading", [
      q({ id: "r-1", subject: "act-reading", text_fidelity: "ok", passage: "A" }),
      q({ id: "r-2", subject: "act-reading", text_fidelity: "ok", passage: "A" }),
    ]),
    section(
      "science",
      "Science",
      [
        q(
          {
            id: "s-1",
            subject: "act-science",
            text_fidelity: "ok",
            passage: "P1",
          },
          { is_figure: true },
        ),
        q(
          {
            id: "s-2",
            subject: "act-science",
            text_fidelity: "ok",
            passage: "P1",
          },
          { is_figure: true },
        ),
        q({ id: "s-3", subject: "act-science", text_fidelity: "ok" }),
      ],
      [FIGURE_PASSAGE],
    ),
  ],
};
