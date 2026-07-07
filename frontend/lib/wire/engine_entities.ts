/**
 * Subject-Coach engine — pure entity + contract shapes (wire kernel).
 *
 * These are the vendor-neutral data shapes the seven ADR-0006 engine ports
 * exchange. They are NOT mirrored from a Python `agent_ui_adapter/wire/` module
 * (unlike the chat wire shapes) — the engine is a Frontend-Ring-local concern
 * (ADR-0005: learner-facing engine runs on-device, local-first). They live in
 * `wire/` for the same reason every other shape does: pure Zod, zero outward
 * dependencies, imported by ports/translators/adapters but importing nothing
 * from them (Rule W1).
 *
 * Naming: snake_case fields to match the Drizzle row columns 1:1
 * (`schema.pg.ts` / `schema.sqlite.ts`), so a repo adapter maps a row to one of
 * these shapes with no key renaming. camelCase happens only in a translator on
 * the way to a view-model (Rule W6), never here.
 *
 * The single hand-pinned contract is `Verdict` (the grading return shape,
 * ADR-0006): generic enough for a future symbolic/numeric grader
 * (`canonical_answer`) without being abstract now (English uses `correct_letter`
 * + `rationale_key`).
 *
 * Import rule (W1): this module imports only `zod`. No React, no SDK, no
 * browser API.
 */

import { z } from "zod";

/** Default subject discriminator — the OCP seam (engine spec FR-H1). */
export const DEFAULT_SUBJECT = "act-english";

// --- skill ---------------------------------------------------------------

/** One taxonomy bucket (English: 'punctuation', 'rhetoric', ...). */
export const Skill = z.object({
  id: z.string(),
  subject: z.string(),
  key: z.string(),
  name: z.string(),
  share_of_test_pct: z.number(),
  accent_var: z.string(),
  description: z.string(),
  order: z.number().int(),
});
export type Skill = z.infer<typeof Skill>;

// --- question ------------------------------------------------------------

/** One answer choice. English: choice A is "NO CHANGE" (`is_no_change`). */
export const Choice = z.object({
  letter: z.string(),
  label: z.string(),
  is_no_change: z.boolean().default(false),
});
export type Choice = z.infer<typeof Choice>;

/**
 * One item. `reviewed = false` rows MUST NOT reach a learner (engine spec
 * FR-B*); `QuestionRepo.nextReviewed` returns reviewed items only. `item_type`
 * drives the client renderer registry, never a `switch(subject)` (FR-H2).
 */
export const Question = z.object({
  id: z.string(),
  subject: z.string(),
  skill_id: z.string(),
  difficulty: z.number().int(), // 1..5
  context_html: z.string(),
  stem: z.string(),
  choices: z.array(Choice),
  answer_letter: z.string(),
  // { A: "...", B: "...", ... } per-choice rationale keyed by letter.
  per_choice_rationale: z.record(z.string(), z.string()),
  why_correct_md: z.string(),
  why_tempted_md: z.string(),
  rule_md: z.string(),
  item_type: z.string(),
  reviewed: z.boolean(),
  generated_by: z.string(),
});
export type Question = z.infer<typeof Question>;

/**
 * The four answer-bearing `Question` fields excluded from the coach's
 * pre-submit context (ADR-0012 / agent spec FR-19). Keyed to the schema at
 * compile time via `satisfies` — renaming a field here or on `Question`
 * breaks the build, and the sanitizer lock test freezes the full key set so
 * a NEW field forces an explicit answer-bearing triage.
 */
export const QUESTION_ANSWER_BEARING_FIELDS = [
  "answer_letter",
  "per_choice_rationale",
  "why_correct_md",
  "why_tempted_md",
] as const satisfies readonly (keyof Question)[];

// --- hint (ADR-0014) ------------------------------------------------------

/**
 * One hint-ladder rung (ADR-0012/ADR-0014, spec FR-12/FR-20). The rung union
 * keeps the assertion rung (4) UNREPRESENTABLE at the wire — probe (1),
 * conceptual (2), directive (3) only. `reviewed = false` rows MUST NOT reach
 * a learner; `HintRepo.list` serves reviewed rungs only. `generated_by` is
 * `"authored"` or `"<model>@<run_id>"` (generator provenance).
 */
export const Hint = z.object({
  id: z.string(),
  subject: z.string(),
  question_id: z.string(),
  rung: z.union([z.literal(1), z.literal(2), z.literal(3)]),
  body_md: z.string().min(1),
  reviewed: z.boolean(),
  generated_by: z.string(),
});
export type Hint = z.infer<typeof Hint>;

// --- test_item + test_blueprint (Phase 6, ADR-0015) ----------------------

/**
 * One governed exam item (ADR-0015 clause 1). Question-shaped, but a SEPARATE
 * entity + table from `Question` so practice scheduling
 * (`QuestionRepo.nextReviewed`) is structurally unable to serve an exam item.
 * `reviewed = false` rows MUST NOT reach a learner; `TestItemRepo.listReviewed`
 * serves reviewed rows only. `generated_by` is `"<model>@<run_id>"` on a
 * reviewed row (never `"test01-import"` — that lives only on unpromoted seed
 * rows). `reviewed` is earned by the Python cascade, never self-asserted.
 *
 * TEACHING FIELDS (ADR-0021 schema extension, spec FR-C1 — amends the minimal
 * exam shape). The bank now also serves the PRACTICE quiz via the
 * `TestItemQuestionRepo` adapter, and the Feedback screen renders
 * `per_choice_rationale` + `rule_md` (`feedback_vm.ts`), so a bank row must
 * carry the full teaching payload — required and non-empty at parse, making
 * the `TestItem→Question` mapping lossless. `stem_md` maps to `Question.stem`;
 * `context_html` is the passage with the underlined span.
 */
export const TestItem = z.object({
  id: z.string(),
  subject: z.string(),
  skill_id: z.string(),
  difficulty: z.number().int(), // 1..5
  context_html: z.string().min(1),
  stem_md: z.string().min(1),
  choices: z.array(Choice).min(4),
  answer_letter: z.string(),
  // { A: "...", B: "...", ... } per-choice rationale keyed by letter (FR-E3).
  per_choice_rationale: z.record(z.string(), z.string()),
  why_correct_md: z.string().min(1),
  why_tempted_md: z.string().min(1),
  rule_md: z.string().min(1),
  item_type: z.string().min(1),
  reviewed: z.boolean(),
  generated_by: z.string(),
});
export type TestItem = z.infer<typeof TestItem>;

/** One scale-band row (raw-score range → scaled score). */
export const ScaleBand = z.object({
  raw_min: z.number().int(),
  raw_max: z.number().int(),
  scale: z.number().int(),
});
export type ScaleBand = z.infer<typeof ScaleBand>;

const SKILL_MIX_TOLERANCE = 1e-6;

/**
 * A test-form blueprint (ADR-0013 §8.2 / ADR-0015 clause 2). The seeded
 * assembler draws a byte-reproducible form from `(blueprint_id, seed)` over a
 * fixed reviewed bank. Validation is the FR-24.1 gate: `skill_mix` weights must
 * sum to 1.0 (within float tolerance), `count > 0`, `scale_band_table`
 * non-empty, `seed` present — a malformed blueprint throws at parse, never a
 * silently clamped or partially applied form.
 */
export const TestBlueprint = z
  .object({
    id: z.string(),
    subject: z.string(),
    skill_mix: z.record(z.string(), z.number()),
    difficulty_dist: z.record(z.string(), z.number()),
    count: z.number().int().positive(),
    minutes: z.number().int().positive(),
    scale_band_table: z.array(ScaleBand).min(1),
    pass_criteria: z.record(z.string(), z.unknown()).optional(),
    seed: z.number().int(),
  })
  .refine(
    (bp) => {
      const sum = Object.values(bp.skill_mix).reduce((a, b) => a + b, 0);
      return Math.abs(sum - 1.0) <= SKILL_MIX_TOLERANCE;
    },
    { message: "skill_mix weights must sum to 1.0", path: ["skill_mix"] },
  );
export type TestBlueprint = z.infer<typeof TestBlueprint>;

// --- quiz_session --------------------------------------------------------

export const SessionMode = z.enum(["adaptive", "drill", "review"]);
export type SessionMode = z.infer<typeof SessionMode>;

/** One drill/adaptive/review session; score tally is set on close (FR-D3). */
export const QuizSession = z.object({
  id: z.string(),
  subject: z.string(),
  learner_id: z.string(),
  mode: SessionMode,
  skill_focus: z.string().nullable(),
  started_at: z.string(), // ISO 8601 on the wire (Rule: Intl + ISO strings)
  ended_at: z.string().nullable(),
  score_correct: z.number().int(),
  score_total: z.number().int(),
});
export type QuizSession = z.infer<typeof QuizSession>;

// --- attempt -------------------------------------------------------------

/** Append-only history of one answered item (FR-D2). */
export const Attempt = z.object({
  id: z.string(),
  subject: z.string(),
  session_id: z.string(),
  question_id: z.string(),
  chosen_letter: z.string(),
  correct: z.boolean(),
  elapsed_ms: z.number().int(),
  used_hint: z.boolean(),
  created_at: z.string(),
});
export type Attempt = z.infer<typeof Attempt>;

/** The fields a caller supplies to record an attempt (id + created_at are engine-assigned). */
export const AttemptInput = Attempt.omit({ id: true, created_at: true });
export type AttemptInput = z.infer<typeof AttemptInput>;

// --- skill_state ---------------------------------------------------------

/**
 * The adaptivity source of truth (FR-A2). The Scheduler (FSRS) port is the
 * ONLY writer. One row per (subject, skill, learner).
 *
 * `mastery`, `fsrs_stability`, `fsrs_difficulty`, `due_at`, `last_seen` are the
 * vendor-neutral projection the rest of the engine reads (UI, weakest-due pick).
 * `fsrs_card` is the OPAQUE full FSRS card snapshot the Scheduler round-trips so
 * the card's state machine (state/reps/lapses/learning_steps/…) advances across
 * reviews instead of resetting to New each time. It is `unknown` precisely so no
 * FSRS type leaks into the wire kernel (Rule W1 / F-R8): only the Scheduler
 * adapter ever parses it back into a card; everyone else treats it as opaque.
 */
export const SkillState = z.object({
  subject: z.string(),
  skill_id: z.string(),
  learner_id: z.string(),
  mastery: z.number(), // 0..1
  last_seen: z.string().nullable(),
  fsrs_stability: z.number(),
  fsrs_difficulty: z.number(),
  due_at: z.string(),
  // Opaque FSRS card snapshot (null before the first review). Only the FsrsScheduler
  // adapter reads/writes this; it is never inspected outside the vendor boundary.
  fsrs_card: z.unknown().nullable().default(null),
});
export type SkillState = z.infer<typeof SkillState>;

// --- tutorial / content_string / progress_point --------------------------

/** "Rule in one line" + examples for a skill; same reviewed-gate as question. */
export const Tutorial = z.object({
  id: z.string(),
  subject: z.string(),
  skill_id: z.string(),
  body_md: z.string(),
  examples: z.array(z.string()),
  generated_from: z.string(),
  reviewed: z.boolean(),
});
export type Tutorial = z.infer<typeof Tutorial>;

/** Sampled progress point for the trend line (UI spec FR-I1). */
export const ProgressPoint = z.object({
  id: z.string(),
  subject: z.string(),
  learner_id: z.string(),
  at: z.string(),
  projected_score: z.number(),
  items_reviewed: z.number().int(),
});
export type ProgressPoint = z.infer<typeof ProgressPoint>;

// --- Verdict (the one pinned grading contract, ADR-0006) -----------------

/**
 * The grading return shape. `correct` is always present. English fills
 * `correct_letter` (canonical answer) + `rationale_key` (which per-choice
 * rationale to surface). `canonical_answer` is reserved for a future
 * symbolic/numeric grader and stays absent for English (FR-C4).
 */
export const Verdict = z.object({
  correct: z.boolean(),
  correct_letter: z.string().optional(),
  canonical_answer: z.string().optional(),
  rationale_key: z.string().optional(),
});
export type Verdict = z.infer<typeof Verdict>;

/** The answer a learner submits for grading. `letter` null = no selection (FR-D2a). */
export const Answer = z.object({
  letter: z.string().nullable(),
});
export type Answer = z.infer<typeof Answer>;

/** Scheduler pick: which (skill, question) to serve next (FR-A1). */
export const NextItem = z.object({
  skill_id: z.string(),
  question_id: z.string(),
});
export type NextItem = z.infer<typeof NextItem>;

/** Session close → recommended next (skill + mode), computed from skill_state (FR-D6). */
export const RecommendedNext = z.object({
  skill_id: z.string(),
  mode: SessionMode,
});
export type RecommendedNext = z.infer<typeof RecommendedNext>;
