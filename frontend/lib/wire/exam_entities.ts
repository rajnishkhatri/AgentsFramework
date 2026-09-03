/**
 * Exam-module wire kernel (ADR-0040, spec §4.1 / FR-9).
 *
 * Pure Zod, zero outward dependencies (Rule W1). Snake_case to match the
 * forthcoming exam_* columns. Extends the existing `Question` shape with
 * exam-only reporting fields — does not change `Question`.
 */

import { z } from "zod";
import { Question } from "./engine_entities";

export const ExamBlueprint = z.enum([
  "test01",
  "preact-secure-legacy",
  "act-enhanced",
]);
export type ExamBlueprint = z.infer<typeof ExamBlueprint>;

export const ExamSectionCode = z.enum([
  "english",
  "math",
  "reading",
  "science",
]);
export type ExamSectionCode = z.infer<typeof ExamSectionCode>;

/** Opaque server-resolved image ref (ADR-0042 / spec §4.1). */
export const AssetRef = z.object({
  store: z.literal("form-image"),
  form_id: z.string().min(1),
  key: z.string().min(1),
});
export type AssetRef = z.infer<typeof AssetRef>;

export const ExamQuestion = Question.extend({
  reporting_category: z.string().nullable(),
  scored: z.boolean(),
  passage: z.string().nullable(),
  image: AssetRef.nullable().default(null),
});
export type ExamQuestion = z.infer<typeof ExamQuestion>;

export const ExamPassage = z.object({
  label: z.string(),
  title: z.string().nullable(),
  intro: z.string().nullable(),
  text: z.string().nullable(),
  image: AssetRef.nullable(),
  question_numbers: z.array(z.number().int()),
});
export type ExamPassage = z.infer<typeof ExamPassage>;

export const ExamSection = z.object({
  code: ExamSectionCode,
  title: z.string(),
  minutes: z.number().positive(),
  choice_count: z.union([z.literal(4), z.literal(5)]),
  directions: z.string(),
  composite: z.boolean(),
  scale_table: z.record(z.string(), z.number()).nullable(),
  questions: z.array(ExamQuestion),
  passages: z.array(ExamPassage).default([]),
});
export type ExamSection = z.infer<typeof ExamSection>;

export const ExamFormDelivery = z.enum(["client-bundled", "asset-served"]);
export type ExamFormDelivery = z.infer<typeof ExamFormDelivery>;

export const ExamForm = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  blueprint: ExamBlueprint,
  composite_sections: z.array(ExamSectionCode),
  sections: z.array(ExamSection),
  delivery: ExamFormDelivery.default("client-bundled"),
});
export type ExamForm = z.infer<typeof ExamForm>;

/** Client-facing asset-served payload: .strict() and no answer-bearing fields (FR-P2-3/8). */
export const ClientExamQuestion = ExamQuestion.omit({
  answer_letter: true,
  per_choice_rationale: true,
  why_correct_md: true,
  why_tempted_md: true,
}).strict();
export type ClientExamQuestion = z.infer<typeof ClientExamQuestion>;

export const ClientExamSection = ExamSection.extend({
  questions: z.array(ClientExamQuestion),
});
export type ClientExamSection = z.infer<typeof ClientExamSection>;

export const ClientExamForm = ExamForm.extend({
  sections: z.array(ClientExamSection),
}).strict();
export type ClientExamForm = z.infer<typeof ClientExamForm>;

export const ExamRun = z.object({
  id: z.string().min(1),
  learner_id: z.string().min(1),
  form_id: z.string().min(1),
  created_at: z.string().min(1),
  composite: z.number().nullable(),
});
export type ExamRun = z.infer<typeof ExamRun>;

export const ExamSectionAttemptStatus = z.enum([
  "not_started",
  "in_progress",
  "submitted",
  "expired",
]);
export type ExamSectionAttemptStatus = z.infer<typeof ExamSectionAttemptStatus>;

export const ExamSectionAttempt = z.object({
  run_id: z.string().min(1),
  section_code: ExamSectionCode,
  status: ExamSectionAttemptStatus,
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
  deadline_at: z.string().nullable(),
  raw_correct: z.number().int().nullable(),
  raw_scored_total: z.number().int().nullable(),
  scale_score: z.number().nullable(),
  time_remaining_ms_at_submit: z.number().int().nullable(),
});
export type ExamSectionAttempt = z.infer<typeof ExamSectionAttempt>;

export const ExamRunItem = z.object({
  run_id: z.string().min(1),
  section_code: ExamSectionCode,
  question_id: z.string().min(1),
  ordinal: z.number().int().nonnegative(),
  chosen_letter: z.string().nullable(),
  correct: z.boolean().nullable(),
  dwell_ms: z.number().nonnegative(),
  visits: z.number().int().nonnegative(),
  answer_changes: z.number().int().nonnegative(),
  first_answered_at: z.string().nullable(),
  dwell_at_first_answer_ms: z.number().nonnegative().nullable(),
  flagged_in_section: z.boolean(),
  bookmarked: z.boolean(),
  updated_at: z.string().min(1),
});
export type ExamRunItem = z.infer<typeof ExamRunItem>;

export const ExamFacetKind = z.enum([
  "subject",
  "category",
  "skill",
  "passage",
  "difficulty",
]);
export type ExamFacetKind = z.infer<typeof ExamFacetKind>;

export const ExamFacetLabel = z.enum([
  "strength",
  "weakness",
  "insufficient_data",
]);
export type ExamFacetLabel = z.infer<typeof ExamFacetLabel>;

export const ExamQuadrants = z.object({
  fast_right: z.number().int().nonnegative(),
  fast_wrong: z.number().int().nonnegative(),
  slow_right: z.number().int().nonnegative(),
  slow_wrong: z.number().int().nonnegative(),
});
export type ExamQuadrants = z.infer<typeof ExamQuadrants>;

export const ExamFacet = z.object({
  kind: ExamFacetKind,
  key: z.string(),
  items: z.number().int().nonnegative(),
  correct: z.number().int().nonnegative(),
  unanswered: z.number().int().nonnegative(),
  accuracy: z.number().nullable(),
  mean_dwell_ms: z.number().nullable(),
  // null when median dwell is undefined (one item, or all dwell 0) — AP-6.
  quadrants: ExamQuadrants.nullable(),
  label: ExamFacetLabel,
});
export type ExamFacet = z.infer<typeof ExamFacet>;

export const ExamPacing = z.object({
  section_code: ExamSectionCode,
  unanswered: z.number().int().nonnegative(),
  trailing_unanswered: z.number().int().nonnegative(),
  time_remaining_ms_at_submit: z.number().int().nullable(),
  pct_over_2x_median_dwell: z.number().nullable(),
});
export type ExamPacing = z.infer<typeof ExamPacing>;

export const ExamRecommendationRule = z.enum([
  "pacing",
  "careless",
  "knowledge_gap",
  "revise_flagged",
]);
export type ExamRecommendationRule = z.infer<typeof ExamRecommendationRule>;

export const ExamRecommendation = z.object({
  rule: ExamRecommendationRule,
  facet_ref: z.string(),
  evidence: z.string(),
  priority: z.number().int(),
});
export type ExamRecommendation = z.infer<typeof ExamRecommendation>;

export const ExamAnalytics = z.object({
  scope: z.object({
    learner_id: z.string().min(1),
    run_id: z.string().nullable(),
  }),
  facets: z.array(ExamFacet),
  pacing: z.array(ExamPacing),
  recommendations: z.array(ExamRecommendation),
});
export type ExamAnalytics = z.infer<typeof ExamAnalytics>;
