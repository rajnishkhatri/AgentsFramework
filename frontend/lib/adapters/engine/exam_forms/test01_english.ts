/**
 * Phase-1 exam form: Test-01 English behind the section-agnostic registry
 * (ADR-0040, FR-6). Wraps the existing TEST01_SERVED_QUESTIONS slice.
 * Delivery = client-bundled (ADR-0041 accepted-risk exemption).
 */

import {
  TEST01_SERVED_MINUTES,
  TEST01_SERVED_QUESTIONS,
} from "../_test01_split";
import type { ExamForm, ExamQuestion } from "../../../wire/exam_entities";

const QUESTIONS: ExamQuestion[] = TEST01_SERVED_QUESTIONS.map((q) => ({
  ...q,
  reporting_category: null,
  scored: true,
  passage: null,
  image: null,
}));

export const TEST01_ENGLISH_FORM_ID = "test01-english";

/** Static form. Load-time asserts run in the registry index. */
export const TEST01_ENGLISH_FORM: ExamForm = {
  id: TEST01_ENGLISH_FORM_ID,
  title: "Test 01 — English",
  blueprint: "test01",
  composite_sections: ["english"],
  delivery: "client-bundled",
  sections: [
    {
      code: "english",
      title: "English",
      minutes: TEST01_SERVED_MINUTES,
      choice_count: 4,
      directions:
        "You will have the time shown to work the English section. " +
        "The clock starts when you tap Begin. You may move freely among " +
        "questions and mark items for review. Unanswered items score 0; " +
        "there is no guessing penalty.",
      composite: true,
      scale_table: null,
      passages: [],
      questions: QUESTIONS,
    },
  ],
};

export const TEST01_ENGLISH_DELIVERY = "client-bundled" as const;
