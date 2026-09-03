/**
 * drizzleEngineDb — the live SDK seam for `EngineDb` (Postgres + SQLite).
 *
 * This is the ONLY engine file that imports the Drizzle query builder + a driver
 * (Rule A1 / F-R2 SDK confinement). It maps Drizzle rows → the pure
 * `wire/engine_entities` shapes so no vendor type escapes (Rule A4 / F-R8). The
 * repos and the Scheduler are written against the narrow `EngineDb` interface,
 * so they never see this file's types.
 *
 * @sdk drizzle-orm ^0.45.2
 * @sdk pg ^8.21.0           (Postgres / Neon — canonical store, ADR-0005)
 *
 * Dual-dialect (ADR-0005): the same logical queries run against `schema.pg.ts`
 * (canonical/online) or `schema.sqlite.ts` (on-device twin). Because the two
 * schemas are column-for-column identical (only column TYPES differ), this seam
 * is written once against a dialect-parameterized table set. The on-device
 * SQLite construction lives behind a separate factory (the driver differs); both
 * funnel into the same row-mapping logic.
 *
 * Exam methods (W1-5) are exercised on L2 sqlite (`node:sqlite`) in CI. Real
 * Postgres two-device concurrency is env-gated behind DATABASE_URL (FR-40 / R8).
 */

import {
  and,
  asc,
  desc,
  eq,
  gte,
  isNotNull,
  isNull,
  lte,
  notInArray,
  sql,
} from "drizzle-orm";
import { drizzle as drizzlePg } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import { pgPoolMax, toNodePgConnectionString } from "@/lib/adapters/db/node_pg_url";
import { mergeExamDwell } from "../../../../components/exam/exam_dwell_merge";
import {
  EngineError,
  EngineNotFoundError,
  EngineRepoError,
} from "../../../ports/engine/errors";
import type {
  Attempt,
  Hint,
  ProgressPoint,
  Question,
  QuizSession,
  Skill,
  SkillAccuracyRow,
  SkillState,
  TestBlueprint,
  TestItem,
  Tutorial,
} from "../../../wire/engine_entities";
import type {
  ExamRun,
  ExamRunItem,
  ExamSectionAttempt,
  ExamSectionCode,
} from "../../../wire/exam_entities";
import {
  attachExamReviewReveal,
  loadExamFormForClient,
  loadExamFormKeys,
} from "../exam_form_load";
import "../exam_forms/generated_official_form";
import type {
  EngineDb,
  ExamRunDetail,
  ExamRunListEntry,
  ExamSectionFinishStatus,
  ExamSectionGrades,
  InsertAttemptResult,
  SessionClosePatch,
} from "./engine_db";
import * as pg from "./schema.pg";
import * as sqliteSchema from "./schema.sqlite";

/** The nine exam methods W1-5 lands on both dialects. */
export type ExamEngineDb = Pick<
  EngineDb,
  | "insertExamRun"
  | "listExamRunsByLearner"
  | "getExamRun"
  | "beginExamSection"
  | "upsertExamRunItems"
  | "finishExamSection"
  | "setExamRunComposite"
  | "setExamBookmark"
  | "listExamRunItemsByLearner"
>;

type ExamTables = {
  examRun: typeof pg.examRun | typeof sqliteSchema.examRun;
  examSectionAttempt:
    | typeof pg.examSectionAttempt
    | typeof sqliteSchema.examSectionAttempt;
  examRunItem: typeof pg.examRunItem | typeof sqliteSchema.examRunItem;
};

type ExamDialect = "pg" | "sqlite";

/**
 * SQLite twin of the exam store (ADR-0005 / W1-5). The driver is supplied by
 * the caller so this file does not import `node:sqlite`.
 */
export function sqliteExamEngineDbFrom(db: unknown): ExamEngineDb {
  return createExamMethods(db, sqliteSchema, "sqlite");
}

// --- row mappers (Drizzle row → wire shape). Timestamps → ISO strings. ---

function isoOf(value: unknown): string {
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "string") return value;
  if (typeof value === "number") return new Date(value).toISOString();
  return new Date().toISOString();
}

function isoOrNull(value: unknown): string | null {
  return value == null ? null : isoOf(value);
}

function toSkill(r: Record<string, unknown>): Skill {
  return {
    id: String(r.id),
    subject: String(r.subject),
    key: String(r.key),
    name: String(r.name),
    share_of_test_pct: Number(r.share_of_test_pct ?? 0),
    accent_var: String(r.accent_var ?? ""),
    description: String(r.description ?? ""),
    order: Number(r.order ?? 0),
  };
}

function toQuestion(r: Record<string, unknown>): Question {
  return {
    id: String(r.id),
    subject: String(r.subject),
    skill_id: String(r.skill_id),
    difficulty: Number(r.difficulty ?? 3),
    context_html: String(r.context_html ?? ""),
    stem: String(r.stem ?? ""),
    choices: (r.choices as Question["choices"]) ?? [],
    answer_letter: String(r.answer_letter),
    per_choice_rationale:
      (r.per_choice_rationale as Record<string, string>) ?? {},
    why_correct_md: String(r.why_correct_md ?? ""),
    why_tempted_md: String(r.why_tempted_md ?? ""),
    rule_md: String(r.rule_md ?? ""),
    item_type: String(r.item_type ?? "underlined-span-mc"),
    misconception: r.misconception == null ? null : String(r.misconception),
    reviewed: Boolean(r.reviewed),
    generated_by: String(r.generated_by ?? ""),
  };
}

function toHint(r: Record<string, unknown>): Hint {
  const letter = r.choice_letter;
  return {
    id: String(r.id),
    subject: String(r.subject),
    question_id: String(r.question_id),
    choice_letter:
      letter == null || letter === ""
        ? null
        : (String(letter) as Hint["choice_letter"]),
    rung: Number(r.rung) as Hint["rung"],
    body_md: String(r.body_md ?? ""),
    reviewed: Boolean(r.reviewed),
    generated_by: String(r.generated_by ?? ""),
  };
}

function toTestItem(r: Record<string, unknown>): TestItem {
  return {
    id: String(r.id),
    subject: String(r.subject),
    skill_id: String(r.skill_id),
    difficulty: Number(r.difficulty ?? 3),
    context_html: String(r.context_html ?? ""),
    stem_md: String(r.stem_md ?? ""),
    choices: (r.choices as TestItem["choices"]) ?? [],
    answer_letter: String(r.answer_letter),
    // Teaching fields (ADR-0021): required for the practice-serving path —
    // the Feedback screen renders per_choice_rationale + rule_md.
    per_choice_rationale:
      (r.per_choice_rationale as TestItem["per_choice_rationale"]) ?? {},
    why_correct_md: String(r.why_correct_md ?? ""),
    why_tempted_md: String(r.why_tempted_md ?? ""),
    rule_md: String(r.rule_md ?? ""),
    item_type: String(r.item_type ?? ""),
    misconception: r.misconception == null ? null : String(r.misconception),
    reviewed: Boolean(r.reviewed),
    generated_by: String(r.generated_by ?? ""),
  };
}

function toTestBlueprint(r: Record<string, unknown>): TestBlueprint {
  return {
    id: String(r.id),
    subject: String(r.subject),
    skill_mix: (r.skill_mix as TestBlueprint["skill_mix"]) ?? {},
    difficulty_dist: (r.difficulty_dist as TestBlueprint["difficulty_dist"]) ?? {},
    count: Number(r.count),
    minutes: Number(r.minutes),
    scale_band_table:
      (r.scale_band_table as TestBlueprint["scale_band_table"]) ?? [],
    ...(r.pass_criteria != null
      ? { pass_criteria: r.pass_criteria as Record<string, unknown> }
      : {}),
    seed: Number(r.seed),
  };
}

function toSession(r: Record<string, unknown>): QuizSession {
  return {
    id: String(r.id),
    subject: String(r.subject),
    learner_id: String(r.learner_id),
    mode: r.mode as QuizSession["mode"],
    skill_focus: r.skill_focus == null ? null : String(r.skill_focus),
    started_at: isoOf(r.started_at),
    ended_at: isoOrNull(r.ended_at),
    score_correct: Number(r.score_correct ?? 0),
    score_total: Number(r.score_total ?? 0),
    // S3 bounded length: a legacy row (added before the column) has no
    // `target_count` → maps to null = endless (FR-3). Otherwise carry the int.
    target_count: r.target_count == null ? null : Number(r.target_count),
    current_question_id:
      r.current_question_id == null ? null : String(r.current_question_id),
  };
}

function toAttempt(r: Record<string, unknown>): Attempt {
  const resolutionRaw = r.resolution;
  const resolution =
    resolutionRaw == null || resolutionRaw === ""
      ? null
      : (String(resolutionRaw) as Attempt["resolution"]);
  return {
    id: String(r.id),
    subject: String(r.subject),
    session_id: String(r.session_id),
    question_id: String(r.question_id),
    chosen_letter: String(r.chosen_letter),
    correct: Boolean(r.correct),
    elapsed_ms: Number(r.elapsed_ms ?? 0),
    used_hint: Boolean(r.used_hint),
    created_at: isoOf(r.created_at),
    resolution,
    idempotency_key:
      r.idempotency_key == null ? null : String(r.idempotency_key),
  };
}

function toSkillState(r: Record<string, unknown>): SkillState {
  return {
    subject: String(r.subject),
    skill_id: String(r.skill_id),
    learner_id: String(r.learner_id),
    mastery: Number(r.mastery ?? 0),
    last_seen: isoOrNull(r.last_seen),
    fsrs_stability: Number(r.fsrs_stability ?? 0),
    fsrs_difficulty: Number(r.fsrs_difficulty ?? 0),
    due_at: isoOf(r.due_at),
    fsrs_card: r.fsrs_card ?? null, // opaque JSON; only the Scheduler parses it
  };
}

function toTutorial(r: Record<string, unknown>): Tutorial {
  const optStr = (v: unknown): string | undefined =>
    v == null ? undefined : String(v);
  return {
    id: String(r.id),
    subject: String(r.subject),
    skill_id: String(r.skill_id),
    body_md: String(r.body_md ?? ""),
    examples: (r.examples as string[]) ?? [],
    generated_from: String(r.generated_from ?? "rule"),
    reviewed: Boolean(r.reviewed),
    ground_md: optStr(r.ground_md),
    pitfall_md: optStr(r.pitfall_md),
    question_md: optStr(r.question_md),
    self_explain_prompt: optStr(r.self_explain_prompt),
    worked_example:
      r.worked_example == null
        ? undefined
        : (r.worked_example as Tutorial["worked_example"]),
    completion_try:
      r.completion_try == null
        ? undefined
        : (r.completion_try as Tutorial["completion_try"]),
    annotated_examples:
      r.annotated_examples == null
        ? undefined
        : (r.annotated_examples as Tutorial["annotated_examples"]),
  };
}

/** Exported for L1 round-trip tests (E1a FR-8b); production callers use getTutorial. */
export { toTutorial };

function toProgressPoint(r: Record<string, unknown>): ProgressPoint {
  return {
    id: String(r.id),
    subject: String(r.subject),
    learner_id: String(r.learner_id),
    at: isoOf(r.at),
    projected_score: Number(r.projected_score ?? 0),
    items_reviewed: Number(r.items_reviewed ?? 0),
  };
}

function examIsoOf(value: unknown): string {
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "string") return value;
  if (typeof value === "number") {
    // sqlite `unixepoch()` / timestamp-mode integers are seconds.
    const ms = value < 1e12 ? value * 1000 : value;
    return new Date(ms).toISOString();
  }
  throw new EngineRepoError(`exam timestamp unreadable: ${typeof value}`);
}

function examIsoOrNull(value: unknown): string | null {
  return value == null ? null : examIsoOf(value);
}

function examBoolOf(value: unknown): boolean {
  return value === true || value === 1 || value === "1";
}

function examBoolOrNull(value: unknown): boolean | null {
  return value == null ? null : examBoolOf(value);
}

function toExamRun(r: Record<string, unknown>): ExamRun {
  return {
    id: String(r.id),
    learner_id: String(r.learner_id),
    form_id: String(r.form_id),
    created_at: examIsoOf(r.created_at),
    composite: r.composite == null ? null : Number(r.composite),
  };
}

function toExamSectionAttempt(r: Record<string, unknown>): ExamSectionAttempt {
  return {
    run_id: String(r.run_id),
    section_code: r.section_code as ExamSectionCode,
    status: r.status as ExamSectionAttempt["status"],
    started_at: examIsoOrNull(r.started_at),
    finished_at: examIsoOrNull(r.finished_at),
    deadline_at: examIsoOrNull(r.deadline_at),
    raw_correct: r.raw_correct == null ? null : Number(r.raw_correct),
    raw_scored_total:
      r.raw_scored_total == null ? null : Number(r.raw_scored_total),
    scale_score: r.scale_score == null ? null : Number(r.scale_score),
    time_remaining_ms_at_submit:
      r.time_remaining_ms_at_submit == null
        ? null
        : Number(r.time_remaining_ms_at_submit),
  };
}

function toExamRunItem(r: Record<string, unknown>): ExamRunItem {
  return {
    run_id: String(r.run_id),
    section_code: r.section_code as ExamSectionCode,
    question_id: String(r.question_id),
    ordinal: Number(r.ordinal),
    chosen_letter: r.chosen_letter == null ? null : String(r.chosen_letter),
    correct: examBoolOrNull(r.correct),
    dwell_ms: Number(r.dwell_ms ?? 0),
    visits: Number(r.visits ?? 0),
    answer_changes: Number(r.answer_changes ?? 0),
    first_answered_at: examIsoOrNull(r.first_answered_at),
    dwell_at_first_answer_ms:
      r.dwell_at_first_answer_ms == null
        ? null
        : Number(r.dwell_at_first_answer_ms),
    flagged_in_section: examBoolOf(r.flagged_in_section),
    bookmarked: examBoolOf(r.bookmarked),
    updated_at: examIsoOf(r.updated_at),
  };
}

function examDateOrNull(iso: string | null): Date | null {
  return iso == null ? null : new Date(iso);
}

function itemInsertValues(row: ExamRunItem) {
  return {
    run_id: row.run_id,
    section_code: row.section_code,
    question_id: row.question_id,
    ordinal: row.ordinal,
    chosen_letter: row.chosen_letter,
    correct: row.correct,
    dwell_ms: row.dwell_ms,
    visits: row.visits,
    answer_changes: row.answer_changes,
    first_answered_at: examDateOrNull(row.first_answered_at),
    dwell_at_first_answer_ms: row.dwell_at_first_answer_ms,
    flagged_in_section: row.flagged_in_section,
    bookmarked: row.bookmarked,
    updated_at: new Date(row.updated_at),
  };
}

function isUniqueViolation(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return /unique|UNIQUE|23505|PRIMARY KEY/i.test(msg);
}

/**
 * Dialect-parameterized exam store (pg + sqlite). Upserts call mergeExamDwell
 * (do not fork). begin uses onConflictDoNothing (keep-first); item writes use
 * onConflictDoUpdate. pg locks the run row so two devices serialize (FR-40).
 */
function createExamMethods(
  db: unknown,
  t: ExamTables,
  dialect: ExamDialect,
): ExamEngineDb {
  const client = db as {
    select: () => {
      from: (table: unknown) => unknown;
    };
    insert: (table: unknown) => unknown;
    update: (table: unknown) => unknown;
    execute: (q: unknown) => Promise<unknown>;
    transaction: <T>(fn: (tx: unknown) => Promise<T>) => Promise<T>;
  };

  const wrap = async <T>(op: string, p: Promise<T>): Promise<T> => {
    try {
      return await p;
    } catch (err) {
      if (err instanceof EngineError) throw err;
      const detail = err instanceof Error ? err.message : String(err);
      throw new EngineRepoError(`engine db ${op} failed: ${detail}`);
    }
  };

  const q = (tx: unknown = client) => tx as typeof client;

  async function lockExamRun(tx: unknown, runId: string): Promise<void> {
    if (dialect !== "pg") return;
    await q(tx).execute(
      sql`SELECT 1 FROM ${t.examRun} WHERE ${t.examRun.id} = ${runId} FOR UPDATE`,
    );
  }

  async function selectOwnedRun(
    tx: unknown,
    learnerId: string,
    runId: string,
  ): Promise<ExamRun | null> {
    const rows = (await (
      q(tx)
        .select()
        .from(t.examRun) as {
        where: (c: unknown) => { limit: (n: number) => Promise<unknown[]> };
      }
    )
      .where(and(eq(t.examRun.id, runId), eq(t.examRun.learner_id, learnerId)))
      .limit(1)) as Record<string, unknown>[];
    const first = rows[0];
    return first ? toExamRun(first) : null;
  }

  async function requireOwnedRun(
    tx: unknown,
    learnerId: string,
    runId: string,
  ): Promise<ExamRun> {
    const run = await selectOwnedRun(tx, learnerId, runId);
    if (run == null) {
      throw new EngineNotFoundError(`exam run not found: ${runId}`);
    }
    return run;
  }

  async function selectAttempts(
    tx: unknown,
    runId: string,
  ): Promise<ExamSectionAttempt[]> {
    const rows = (await (
      q(tx)
        .select()
        .from(t.examSectionAttempt) as {
        where: (c: unknown) => {
          orderBy: (...o: unknown[]) => Promise<unknown[]>;
        };
      }
    )
      .where(eq(t.examSectionAttempt.run_id, runId))
      .orderBy(asc(t.examSectionAttempt.section_code))) as Record<
      string,
      unknown
    >[];
    return rows.map((r) => toExamSectionAttempt(r));
  }

  async function selectAttempt(
    tx: unknown,
    runId: string,
    section: ExamSectionCode,
  ): Promise<ExamSectionAttempt | null> {
    const rows = (await (
      q(tx)
        .select()
        .from(t.examSectionAttempt) as {
        where: (c: unknown) => { limit: (n: number) => Promise<unknown[]> };
      }
    )
      .where(
        and(
          eq(t.examSectionAttempt.run_id, runId),
          eq(t.examSectionAttempt.section_code, section),
        ),
      )
      .limit(1)) as Record<string, unknown>[];
    const first = rows[0];
    return first ? toExamSectionAttempt(first) : null;
  }

  async function selectItems(
    tx: unknown,
    runId: string,
  ): Promise<ExamRunItem[]> {
    const rows = (await (
      q(tx)
        .select()
        .from(t.examRunItem) as {
        where: (c: unknown) => {
          orderBy: (...o: unknown[]) => Promise<unknown[]>;
        };
      }
    )
      .where(eq(t.examRunItem.run_id, runId))
      .orderBy(asc(t.examRunItem.ordinal), asc(t.examRunItem.question_id))) as Record<
      string,
      unknown
    >[];
    return rows.map((r) => toExamRunItem(r));
  }

  async function selectItem(
    tx: unknown,
    runId: string,
    section: ExamSectionCode,
    questionId: string,
  ): Promise<ExamRunItem | null> {
    const rows = (await (
      q(tx)
        .select()
        .from(t.examRunItem) as {
        where: (c: unknown) => { limit: (n: number) => Promise<unknown[]> };
      }
    )
      .where(
        and(
          eq(t.examRunItem.run_id, runId),
          eq(t.examRunItem.section_code, section),
          eq(t.examRunItem.question_id, questionId),
        ),
      )
      .limit(1)) as Record<string, unknown>[];
    const first = rows[0];
    return first ? toExamRunItem(first) : null;
  }

  return {
    async insertExamRun(learnerId, run) {
      const stored: ExamRun = { ...run, learner_id: learnerId };
      try {
        await wrap(
          "insertExamRun",
          (
            client.insert(t.examRun) as {
              values: (v: unknown) => Promise<unknown>;
            }
          ).values({
            id: stored.id,
            learner_id: stored.learner_id,
            form_id: stored.form_id,
            created_at: new Date(stored.created_at),
            composite: stored.composite,
          }),
        );
      } catch (err) {
        if (isUniqueViolation(err)) {
          throw new EngineRepoError(`duplicate exam run: ${stored.id}`);
        }
        throw err;
      }
    },

    async listExamRunsByLearner(learnerId, formId) {
      const predicates = [eq(t.examRun.learner_id, learnerId)];
      if (formId != null) predicates.push(eq(t.examRun.form_id, formId));
      const rows = (await wrap(
        "listExamRunsByLearner",
        (
          client.select().from(t.examRun) as {
            where: (c: unknown) => {
              orderBy: (...o: unknown[]) => Promise<unknown[]>;
            };
          }
        )
          .where(and(...predicates))
          .orderBy(desc(t.examRun.created_at), asc(t.examRun.id)),
      )) as Record<string, unknown>[];
      const entries: ExamRunListEntry[] = [];
      for (const r of rows) {
        const mapped = toExamRun(r);
        entries.push({
          run: mapped,
          attempts: await selectAttempts(client, mapped.id),
        });
      }
      return entries;
    },

    async getExamRun(learnerId, runId) {
      const run = await selectOwnedRun(client, learnerId, runId);
      if (run == null) return null;
      const keys = await loadExamFormKeys(run.form_id);
      return attachExamReviewReveal(
        {
          run,
          attempts: await selectAttempts(client, runId),
          items: await selectItems(client, runId),
        },
        keys,
      );
    },

    async beginExamSection(learnerId, runId, section, startedAt, deadlineAt) {
      return client.transaction(async (tx) => {
        await requireOwnedRun(tx, learnerId, runId);
        await lockExamRun(tx, runId);
        const existing = await selectAttempt(tx, runId, section);
        if (existing?.status === "in_progress") {
          return existing;
        }
        if (existing?.status === "submitted" || existing?.status === "expired") {
          throw new EngineRepoError(
            `beginExamSection: attempt already ${existing.status}`,
          );
        }
        const others = await selectAttempts(tx, runId);
        if (others.some((a) => a.status === "in_progress")) {
          throw new EngineRepoError(
            "beginExamSection: another section is in progress",
          );
        }
        await wrap(
          "beginExamSection",
          (
            q(tx).insert(t.examSectionAttempt) as {
              values: (v: unknown) => {
                onConflictDoNothing: (c: unknown) => Promise<unknown>;
              };
            }
          )
            .values({
              run_id: runId,
              section_code: section,
              status: "in_progress",
              started_at: new Date(startedAt),
              finished_at: null,
              deadline_at: new Date(deadlineAt),
              raw_correct: null,
              raw_scored_total: null,
              scale_score: null,
              time_remaining_ms_at_submit: null,
            })
            .onConflictDoNothing({
              target: [
                t.examSectionAttempt.run_id,
                t.examSectionAttempt.section_code,
              ],
            }),
        );
        const stored = await selectAttempt(tx, runId, section);
        if (stored == null) {
          throw new EngineRepoError(
            `beginExamSection: attempt missing after insert: ${runId}/${section}`,
          );
        }
        if (stored.status === "submitted" || stored.status === "expired") {
          throw new EngineRepoError(
            `beginExamSection: attempt already ${stored.status}`,
          );
        }
        return stored;
      });
    },

    async upsertExamRunItems(learnerId, runId, section, items) {
      await client.transaction(async (tx) => {
        await requireOwnedRun(tx, learnerId, runId);
        await lockExamRun(tx, runId);
        const attempt = await selectAttempt(tx, runId, section);
        if (attempt?.status !== "in_progress") {
          throw new EngineRepoError(
            "upsertExamRunItems: attempt not in_progress",
          );
        }
        for (const incoming of items) {
          const stamped: ExamRunItem = {
            ...incoming,
            run_id: runId,
            section_code: section,
          };
          const stored = await selectItem(
            tx,
            runId,
            section,
            stamped.question_id,
          );
          const merged =
            stored == null ? stamped : mergeExamDwell(stored, stamped);
          const values = itemInsertValues(merged);
          await wrap(
            "upsertExamRunItems",
            (
              q(tx).insert(t.examRunItem) as {
                values: (v: unknown) => {
                  onConflictDoUpdate: (c: unknown) => Promise<unknown>;
                };
              }
            )
              .values(values)
              .onConflictDoUpdate({
                target: [
                  t.examRunItem.run_id,
                  t.examRunItem.section_code,
                  t.examRunItem.question_id,
                ],
                set: {
                  ordinal: values.ordinal,
                  chosen_letter: values.chosen_letter,
                  correct: values.correct,
                  dwell_ms: values.dwell_ms,
                  visits: values.visits,
                  answer_changes: values.answer_changes,
                  first_answered_at: values.first_answered_at,
                  dwell_at_first_answer_ms: values.dwell_at_first_answer_ms,
                  flagged_in_section: values.flagged_in_section,
                  bookmarked: values.bookmarked,
                  updated_at: values.updated_at,
                },
              }),
          );
        }
      });
    },

    async finishExamSection(
      learnerId,
      runId,
      section,
      status: ExamSectionFinishStatus,
      grades: ExamSectionGrades,
      remainingMs,
    ) {
      return client.transaction(async (tx) => {
        await requireOwnedRun(tx, learnerId, runId);
        await lockExamRun(tx, runId);
        const updated = (await wrap(
          "finishExamSection",
          (
            q(tx).update(t.examSectionAttempt) as {
              set: (v: unknown) => {
                where: (c: unknown) => {
                  returning: () => Promise<unknown[]>;
                };
              };
            }
          )
            .set({
              status,
              finished_at: new Date(),
              raw_correct: grades.raw_correct,
              raw_scored_total: grades.raw_scored_total,
              scale_score: grades.scale_score,
              time_remaining_ms_at_submit: remainingMs,
            })
            .where(
              and(
                eq(t.examSectionAttempt.run_id, runId),
                eq(t.examSectionAttempt.section_code, section),
                eq(t.examSectionAttempt.status, "in_progress"),
              ),
            )
            .returning(),
        )) as Record<string, unknown>[];
        const first = updated[0];
        if (first) return toExamSectionAttempt(first);
        const existing = await selectAttempt(tx, runId, section);
        if (existing == null) {
          throw new EngineNotFoundError(
            `exam section attempt not found: ${runId}/${section}`,
          );
        }
        if (existing.status === "submitted" || existing.status === "expired") {
          return existing;
        }
        throw new EngineRepoError("finishExamSection: attempt not in_progress");
      });
    },

    async setExamRunComposite(learnerId, runId, composite) {
      await requireOwnedRun(client, learnerId, runId);
      await wrap(
        "setExamRunComposite",
        (
          client.update(t.examRun) as {
            set: (v: unknown) => { where: (c: unknown) => Promise<unknown> };
          }
        )
          .set({ composite })
          .where(
            and(eq(t.examRun.id, runId), eq(t.examRun.learner_id, learnerId)),
          ),
      );
    },

    async setExamBookmark(learnerId, runId, section, questionId, bookmarked) {
      await requireOwnedRun(client, learnerId, runId);
      const attempt = await selectAttempt(client, runId, section);
      if (attempt?.status !== "submitted" && attempt?.status !== "expired") {
        throw new EngineRepoError("setExamBookmark: attempt not finished");
      }
      const stored = await selectItem(client, runId, section, questionId);
      if (stored == null) {
        throw new EngineNotFoundError(
          `exam run item not found: ${runId}/${section}/${questionId}`,
        );
      }
      await wrap(
        "setExamBookmark",
        (
          client.update(t.examRunItem) as {
            set: (v: unknown) => { where: (c: unknown) => Promise<unknown> };
          }
        )
          .set({ bookmarked })
          .where(
            and(
              eq(t.examRunItem.run_id, runId),
              eq(t.examRunItem.section_code, section),
              eq(t.examRunItem.question_id, questionId),
            ),
          ),
      );
    },

    async listExamRunItemsByLearner(learnerId) {
      const rows = (await wrap(
        "listExamRunItemsByLearner",
        (
          (
            client.select().from(t.examRunItem) as {
              innerJoin: (table: unknown, on: unknown) => {
                where: (c: unknown) => {
                  orderBy: (...o: unknown[]) => Promise<unknown[]>;
                };
              };
            }
          )
            .innerJoin(t.examRun, eq(t.examRunItem.run_id, t.examRun.id))
            .where(eq(t.examRun.learner_id, learnerId))
            .orderBy(
              asc(t.examRunItem.run_id),
              asc(t.examRunItem.section_code),
              asc(t.examRunItem.ordinal),
              asc(t.examRunItem.question_id),
            )
        ),
      )) as Record<string, unknown>[];
      return rows.map((r) => {
        const src =
          r.exam_run_item != null && typeof r.exam_run_item === "object"
            ? (r.exam_run_item as Record<string, unknown>)
            : r;
        return toExamRunItem(src);
      });
    },
  };
}

type PgDb = ReturnType<typeof drizzlePg>;

/**
 * Build the Postgres-backed `EngineDb` (canonical store). The driver only parses
 * the connection string here; no network round-trip until a query runs, so
 * construction is side-effect-free (matches `neonDrizzleDb`).
 */
export function pgEngineDb(databaseUrl: string): EngineDb {
  if (!databaseUrl || !databaseUrl.trim()) {
    throw new EngineRepoError("pgEngineDb requires a non-empty DATABASE_URL");
  }
  const pool = new Pool({
    connectionString: toNodePgConnectionString(databaseUrl),
    // T R.13 — bounded pool so the engine + threads + marker pools stay
    // under Cloud SQL max_connections=50. Default 5; override via
    // ENGINE_PG_POOL_MAX (clamped to [1, 20]).
    max: pgPoolMax(process.env, 5),
  });
  const db = drizzlePg(pool);
  return pgEngineDbFrom(db);
}

/**
 * The row-mapping seam over an already-constructed pg drizzle client. Split out
 * so an integration test can inject a client against a throwaway database.
 */
export function pgEngineDbFrom(db: PgDb): EngineDb {
  const wrap = <T>(op: string, p: Promise<T>): Promise<T> =>
    p.catch((err) => {
      const detail = err instanceof Error ? err.message : String(err);
      throw new EngineRepoError(`engine db ${op} failed: ${detail}`);
    });

  return {
    async listSkills(subject) {
      const rows = await wrap(
        "listSkills",
        db
          .select()
          .from(pg.skill)
          .where(eq(pg.skill.subject, subject))
          .orderBy(asc(pg.skill.order)),
      );
      return rows.map((r) => toSkill(r as Record<string, unknown>));
    },
    async getSkillByKey(subject, key) {
      const rows = await wrap(
        "getSkillByKey",
        db
          .select()
          .from(pg.skill)
          .where(and(eq(pg.skill.subject, subject), eq(pg.skill.key, key)))
          .limit(1),
      );
      const first = rows[0];
      return first ? toSkill(first as Record<string, unknown>) : null;
    },
    async listSkillIds(subject) {
      const rows = await wrap(
        "listSkillIds",
        db
          .select({ id: pg.skill.id })
          .from(pg.skill)
          .where(eq(pg.skill.subject, subject))
          .orderBy(asc(pg.skill.order), asc(pg.skill.id)),
      );
      return rows.map((r) => String((r as { id: unknown }).id));
    },
    async nextReviewedQuestion(subject, skillId, excludeIds) {
      // S3 served-set (FR-9): a NOT IN predicate on top of the reviewed gate.
      // Added only when non-empty — an empty `NOT IN ()` is invalid SQL and
      // would change today's behaviour, so omitted/empty is a no-op (FR-12).
      const predicates = [
        eq(pg.question.subject, subject),
        eq(pg.question.skill_id, skillId),
        eq(pg.question.reviewed, true), // HARD GATE (FR-B*)
      ];
      if (excludeIds && excludeIds.length > 0) {
        predicates.push(notInArray(pg.question.id, [...excludeIds]));
      }
      const rows = await wrap(
        "nextReviewedQuestion",
        db
          .select()
          .from(pg.question)
          .where(and(...predicates))
          .orderBy(asc(pg.question.difficulty), asc(pg.question.id))
          .limit(1),
      );
      const first = rows[0];
      return first ? toQuestion(first as Record<string, unknown>) : null;
    },
    async getQuestion(id) {
      const rows = await wrap(
        "getQuestion",
        db.select().from(pg.question).where(eq(pg.question.id, id)).limit(1),
      );
      const first = rows[0];
      return first ? toQuestion(first as Record<string, unknown>) : null;
    },
    async insertQuestion(q) {
      await wrap("insertQuestion", db.insert(pg.question).values(q));
    },
    async listReviewedHints(subject, questionId, choiceLetter) {
      // Default to item-level (null) — ADR-0035.
      const letter = choiceLetter ?? null;
      const letterPred =
        letter == null
          ? isNull(pg.hint.choice_letter)
          : eq(pg.hint.choice_letter, letter);
      const rows = await wrap(
        "listReviewedHints",
        db
          .select()
          .from(pg.hint)
          .where(
            and(
              eq(pg.hint.subject, subject),
              eq(pg.hint.question_id, questionId),
              letterPred,
              eq(pg.hint.reviewed, true), // HARD GATE (FR-12/FR-20)
            ),
          )
          .orderBy(asc(pg.hint.rung)),
      );
      return rows.map((r) => toHint(r as Record<string, unknown>));
    },
    async insertHint(h) {
      // Duplicate (question_id, choice_letter, rung) — ADR-0035 partial uqs.
      await wrap(
        "insertHint",
        db.insert(pg.hint).values({
          ...h,
          choice_letter: h.choice_letter ?? null,
        }),
      );
    },
    async listReviewedTestItems(subject) {
      const rows = await wrap(
        "listReviewedTestItems",
        db
          .select()
          .from(pg.testItem)
          .where(
            and(
              eq(pg.testItem.subject, subject),
              eq(pg.testItem.reviewed, true), // HARD GATE (FR-27.1)
            ),
          )
          .orderBy(asc(pg.testItem.id)),
      );
      return rows.map((r) => toTestItem(r as Record<string, unknown>));
    },
    async insertTestItem(item) {
      await wrap("insertTestItem", db.insert(pg.testItem).values(item));
    },
    async getTestBlueprint(id) {
      const rows = await wrap(
        "getTestBlueprint",
        db.select().from(pg.testBlueprint).where(eq(pg.testBlueprint.id, id)).limit(1),
      );
      const first = rows[0];
      return first ? toTestBlueprint(first as Record<string, unknown>) : null;
    },
    async insertTestBlueprint(bp) {
      await wrap("insertTestBlueprint", db.insert(pg.testBlueprint).values(bp));
    },
    async insertSession(s) {
      await wrap(
        "insertSession",
        db.insert(pg.quizSession).values({
          ...s,
          started_at: new Date(s.started_at),
          ended_at: s.ended_at ? new Date(s.ended_at) : null,
        }),
      );
    },
    async getSession(id) {
      const rows = await wrap(
        "getSession",
        db.select().from(pg.quizSession).where(eq(pg.quizSession.id, id)).limit(1),
      );
      const first = rows[0];
      return first ? toSession(first as Record<string, unknown>) : null;
    },
    async patchSessionClose(id, patch: SessionClosePatch) {
      const rows = await wrap(
        "patchSessionClose",
        db
          .update(pg.quizSession)
          .set({
            // Idempotent close: keep the first close timestamp on re-close so
            // ended_at never moves (mirrors the in-memory fake's `?? patch`).
            ended_at: sql`coalesce(${pg.quizSession.ended_at}, ${new Date(patch.ended_at)})`,
            score_correct: patch.score_correct,
            score_total: patch.score_total,
            // T R.12 / FR-B3c: clear the served pointer in the SAME UPDATE so
            // the close is one atomic statement (no partial apply possible).
            current_question_id: null,
          })
          .where(eq(pg.quizSession.id, id))
          .returning(),
      );
      const first = rows[0];
      return first ? toSession(first as Record<string, unknown>) : null;
    },
    async listClosedSessionsByLearner(subject, learnerId, options) {
      const predicates = [
        eq(pg.quizSession.subject, subject),
        eq(pg.quizSession.learner_id, learnerId),
        isNotNull(pg.quizSession.ended_at),
      ];
      if (options?.sinceISO != null) {
        predicates.push(gte(pg.quizSession.ended_at, new Date(options.sinceISO)));
      }
      const rows = await wrap(
        "listClosedSessionsByLearner",
        db
          .select()
          .from(pg.quizSession)
          .where(and(...predicates))
          .orderBy(desc(pg.quizSession.ended_at), asc(pg.quizSession.id)),
      );
      return rows.map((r) => toSession(r as Record<string, unknown>));
    },
    async setSessionCurrentQuestion(sessionId, questionId) {
      await wrap(
        "setSessionCurrentQuestion",
        db
          .update(pg.quizSession)
          .set({ current_question_id: questionId })
          .where(eq(pg.quizSession.id, sessionId)),
      );
    },
    async getNewestOpenSession(subject, learnerId) {
      const rows = await wrap(
        "getNewestOpenSession",
        db
          .select()
          .from(pg.quizSession)
          .where(
            and(
              eq(pg.quizSession.subject, subject),
              eq(pg.quizSession.learner_id, learnerId),
              isNull(pg.quizSession.ended_at),
            ),
          )
          .orderBy(desc(pg.quizSession.started_at), desc(pg.quizSession.id))
          .limit(1),
      );
      const first = rows[0];
      return first ? toSession(first as Record<string, unknown>) : null;
    },
    async insertAttempt(a): Promise<InsertAttemptResult> {
      const values = {
        ...a,
        created_at: new Date(a.created_at),
        idempotency_key: a.idempotency_key ?? null,
      };
      const inserted = await wrap(
        "insertAttempt",
        db
          .insert(pg.attempt)
          .values(values)
          .onConflictDoNothing({
            // Must match attempt_idempotency_uq's partial predicate — without
            // `where`, PG rejects "no unique … matching the ON CONFLICT".
            target: [
              pg.attempt.session_id,
              pg.attempt.question_id,
              pg.attempt.idempotency_key,
            ],
            where: sql`${pg.attempt.idempotency_key} is not null`,
          })
          .returning(),
      );
      if (inserted.length > 0) {
        return {
          status: "inserted",
          attempt: toAttempt(inserted[0] as Record<string, unknown>),
        };
      }
      // Conflict: re-select the stored row (typed already-existed).
      if (a.idempotency_key == null) {
        throw new EngineRepoError(
          "insertAttempt conflict without idempotency_key",
        );
      }
      const existing = await wrap(
        "insertAttempt.reselect",
        db
          .select()
          .from(pg.attempt)
          .where(
            and(
              eq(pg.attempt.session_id, a.session_id),
              eq(pg.attempt.question_id, a.question_id),
              eq(pg.attempt.idempotency_key, a.idempotency_key),
            ),
          )
          .limit(1),
      );
      const row = existing[0];
      if (!row) {
        throw new EngineRepoError(
          "insertAttempt conflict but stored row not found",
        );
      }
      return {
        status: "already-existed",
        attempt: toAttempt(row as Record<string, unknown>),
      };
    },
    async listMisses(subject, learnerId) {
      // Outstanding misses (FR-D4): incorrect attempts that are still the
      // learner's latest attempt for that question_id. A later correct clears
      // the item from the review pool. NOT EXISTS is portable across PG+SQLite
      // (unlike DISTINCT ON). Matches InMemoryEngineDb.listMisses.
      //
      // §6 per-question resolution order: greatest `created_at`, ties broken
      // by greatest `id` (server-assigned PK, stable across devices — the
      // concurrent-device same-ms case). The `NOT EXISTS` predicate therefore
      // excludes a row when a later row has a strictly-greater `created_at`,
      // OR an equal `created_at` with a greater `id`.
      const rows = await wrap(
        "listMisses",
        db
          .select({ attempt: pg.attempt })
          .from(pg.attempt)
          .innerJoin(pg.quizSession, eq(pg.attempt.session_id, pg.quizSession.id))
          .where(
            and(
              eq(pg.attempt.subject, subject),
              eq(pg.attempt.correct, false),
              eq(pg.quizSession.learner_id, learnerId),
              // Scope the session by subject too (matches the in-memory fake):
              // a learner's miss is scoped by BOTH the attempt's subject and its
              // session's subject, so cross-subject/mis-tagged rows can't leak in.
              eq(pg.quizSession.subject, subject),
              sql`NOT EXISTS (
                SELECT 1
                FROM ${pg.attempt} AS later
                INNER JOIN ${pg.quizSession} AS later_sess
                  ON later.session_id = later_sess.id
                WHERE later.question_id = ${pg.attempt.question_id}
                  AND later.subject = ${subject}
                  AND later_sess.learner_id = ${learnerId}
                  AND later_sess.subject = ${subject}
                  AND (
                    later.created_at > ${pg.attempt.created_at}
                    OR (later.created_at = ${pg.attempt.created_at}
                        AND later.id > ${pg.attempt.id})
                  )
              )`,
            ),
          )
          .orderBy(desc(pg.attempt.created_at)),
      );
      return rows.map((r) =>
        toAttempt((r as { attempt: Record<string, unknown> }).attempt),
      );
    },
    async listAlreadyCorrectQuestionIds(subject, learnerId) {
      // FR-E4 — inverse of listMisses: latest attempt per question is correct.
      // §6 order: greatest `created_at`, ties by greatest `id` (same predicate
      // shape as listMisses). question_id-only projection; order not significant.
      const rows = await wrap(
        "listAlreadyCorrectQuestionIds",
        db
          .select({ question_id: pg.attempt.question_id })
          .from(pg.attempt)
          .innerJoin(pg.quizSession, eq(pg.attempt.session_id, pg.quizSession.id))
          .where(
            and(
              eq(pg.attempt.subject, subject),
              eq(pg.attempt.correct, true),
              eq(pg.quizSession.learner_id, learnerId),
              eq(pg.quizSession.subject, subject),
              sql`NOT EXISTS (
                SELECT 1
                FROM ${pg.attempt} AS later
                INNER JOIN ${pg.quizSession} AS later_sess
                  ON later.session_id = later_sess.id
                WHERE later.question_id = ${pg.attempt.question_id}
                  AND later.subject = ${subject}
                  AND later_sess.learner_id = ${learnerId}
                  AND later_sess.subject = ${subject}
                  AND (
                    later.created_at > ${pg.attempt.created_at}
                    OR (later.created_at = ${pg.attempt.created_at}
                        AND later.id > ${pg.attempt.id})
                  )
              )`,
            ),
          ),
      );
      return rows.map((r) =>
        String((r as { question_id: unknown }).question_id),
      );
    },
    async listSessionQuestionIds(sessionId) {
      // The served set (FR-13): every question_id answered in this session, any
      // correctness. A question_id-only projection scoped by session_id — no
      // join (the session id is enough; order is not significant).
      const rows = await wrap(
        "listSessionQuestionIds",
        db
          .select({ question_id: pg.attempt.question_id })
          .from(pg.attempt)
          .where(eq(pg.attempt.session_id, sessionId)),
      );
      return rows.map((r) => String((r as { question_id: unknown }).question_id));
    },
    async listSessionAttempts(sessionId) {
      const rows = await wrap(
        "listSessionAttempts",
        db
          .select()
          .from(pg.attempt)
          .where(eq(pg.attempt.session_id, sessionId))
          .orderBy(asc(pg.attempt.created_at)),
      );
      return (rows as Record<string, unknown>[]).map(toAttempt);
    },
    async listSessionSkillIds(sessionId) {
      // The session's served skills newest-first (S3.1 FR-5): resolve each
      // attempt's question_id → skill_id, order by attempt.created_at desc, then
      // de-dup in JS keeping each skill's newest occurrence. An attempt's
      // question_id may be a `question` id (dev/practice) OR a `test_item` id
      // (the ADR-0021 bank path), so LEFT JOIN both tables and COALESCE the skill
      // — an INNER JOIN on `question` alone would drop every bank attempt and make
      // rotation silently no-op on the live quiz. Each id matches ≤1 row per
      // table, so the left joins yield one row per attempt. Derived from `attempt`
      // only (FR-13).
      const rows = await wrap(
        "listSessionSkillIds",
        db
          .select({
            skill_id: sql<
              string | null
            >`coalesce(${pg.question.skill_id}, ${pg.testItem.skill_id})`,
          })
          .from(pg.attempt)
          .leftJoin(pg.question, eq(pg.attempt.question_id, pg.question.id))
          .leftJoin(pg.testItem, eq(pg.attempt.question_id, pg.testItem.id))
          .where(eq(pg.attempt.session_id, sessionId))
          .orderBy(desc(pg.attempt.created_at)),
      );
      const seen = new Set<string>();
      const skills: string[] = [];
      for (const r of rows) {
        const raw = (r as { skill_id: unknown }).skill_id;
        if (raw == null) continue; // id in neither table — skip (defensive)
        const id = String(raw);
        if (seen.has(id)) continue;
        seen.add(id);
        skills.push(id);
      }
      return skills;
    },
    async accuracyRowsBySkill(subject, learnerId, skillId, sessions) {
      // Per-session on-skill tallies newest-first (E1b-D1). COALESCE join so
      // ADR-0021 bank (test_item) attempts count — an INNER JOIN on `question`
      // alone would drop them. GROUP BY session_id; ORDER BY MAX(created_at)
      // DESC; LIMIT sessions. Derived from `attempt` only (FR-7).
      const rows = await wrap(
        "accuracyRowsBySkill",
        db
          .select({
            session_id: pg.attempt.session_id,
            correct: sql<number>`sum(case when ${pg.attempt.correct} then 1 else 0 end)`,
            total: sql<number>`count(*)`,
            newest_at: sql<Date>`max(${pg.attempt.created_at})`,
          })
          .from(pg.attempt)
          .innerJoin(pg.quizSession, eq(pg.attempt.session_id, pg.quizSession.id))
          .leftJoin(pg.question, eq(pg.attempt.question_id, pg.question.id))
          .leftJoin(pg.testItem, eq(pg.attempt.question_id, pg.testItem.id))
          .where(
            and(
              eq(pg.attempt.subject, subject),
              eq(pg.quizSession.learner_id, learnerId),
              eq(pg.quizSession.subject, subject),
              sql`coalesce(${pg.question.skill_id}, ${pg.testItem.skill_id}) = ${skillId}`,
            ),
          )
          .groupBy(pg.attempt.session_id)
          .orderBy(sql`max(${pg.attempt.created_at}) desc`)
          .limit(sessions),
      );
      return rows.map((r): SkillAccuracyRow => ({
        sessionId: String((r as { session_id: unknown }).session_id),
        correct: Number((r as { correct: unknown }).correct),
        total: Number((r as { total: unknown }).total),
      }));
    },
    async listSkillState(subject, learnerId) {
      const rows = await wrap(
        "listSkillState",
        db
          .select()
          .from(pg.skillState)
          .where(
            and(
              eq(pg.skillState.subject, subject),
              eq(pg.skillState.learner_id, learnerId),
            ),
          ),
      );
      return rows.map((r) => toSkillState(r as Record<string, unknown>));
    },
    async getSkillState(subject, skillId, learnerId) {
      const rows = await wrap(
        "getSkillState",
        db
          .select()
          .from(pg.skillState)
          .where(
            and(
              eq(pg.skillState.subject, subject),
              eq(pg.skillState.skill_id, skillId),
              eq(pg.skillState.learner_id, learnerId),
            ),
          )
          .limit(1),
      );
      const first = rows[0];
      return first ? toSkillState(first as Record<string, unknown>) : null;
    },
    async upsertSkillState(state) {
      await wrap(
        "upsertSkillState",
        db
          .insert(pg.skillState)
          .values({
            ...state,
            last_seen: state.last_seen ? new Date(state.last_seen) : null,
            due_at: new Date(state.due_at),
            fsrs_card: state.fsrs_card ?? null,
          })
          .onConflictDoUpdate({
            target: [
              pg.skillState.subject,
              pg.skillState.skill_id,
              pg.skillState.learner_id,
            ],
            set: {
              mastery: state.mastery,
              last_seen: state.last_seen ? new Date(state.last_seen) : null,
              fsrs_stability: state.fsrs_stability,
              fsrs_difficulty: state.fsrs_difficulty,
              due_at: new Date(state.due_at),
              fsrs_card: state.fsrs_card ?? null,
            },
          }),
      );
    },
    async getContentString(subject, key, locale) {
      const rows = await wrap(
        "getContentString",
        db
          .select({ value: pg.contentString.value })
          .from(pg.contentString)
          .where(
            and(
              eq(pg.contentString.subject, subject),
              eq(pg.contentString.key, key),
              eq(pg.contentString.locale, locale),
            ),
          )
          .limit(1),
      );
      const first = rows[0];
      return first ? String((first as { value: unknown }).value) : null;
    },
    async listContentStrings(subject, locale) {
      const rows = await wrap(
        "listContentStrings",
        db
          .select({ key: pg.contentString.key, value: pg.contentString.value })
          .from(pg.contentString)
          .where(
            and(
              eq(pg.contentString.subject, subject),
              eq(pg.contentString.locale, locale),
            ),
          ),
      );
      return rows.map((r) => ({
        key: String((r as { key: unknown }).key),
        value: String((r as { value: unknown }).value),
      }));
    },
    async getTutorial(subject, skillId) {
      const rows = await wrap(
        "getTutorial",
        db
          .select()
          .from(pg.tutorial)
          .where(
            and(
              eq(pg.tutorial.subject, subject),
              eq(pg.tutorial.skill_id, skillId),
            ),
          )
          .limit(1),
      );
      const first = rows[0];
      return first ? toTutorial(first as Record<string, unknown>) : null;
    },
    async listProgressPoints(subject, learnerId) {
      const rows = await wrap(
        "listProgressPoints",
        db
          .select()
          .from(pg.progressPoint)
          .where(
            and(
              eq(pg.progressPoint.subject, subject),
              eq(pg.progressPoint.learner_id, learnerId),
            ),
          )
          .orderBy(asc(pg.progressPoint.at)),
      );
      return rows.map((r) => toProgressPoint(r as Record<string, unknown>));
    },
    // --- exam (W1-5). Shared merge + .onConflict; positional learnerId. ---
    ...createExamMethods(db, pg, "pg"),
    async getExamFormForClient(_learnerId, formId) {
      return loadExamFormForClient(formId);
    },
    async getExamFormKeys(formId) {
      return loadExamFormKeys(formId);
    },
  };
}

// `lte` is reserved for the on-device SQLite seam's due-window query (added when
// the Capacitor SQLite driver is wired); kept imported so both seams share an
// identical import surface for the dual-dialect parity check.
export const __drizzle_lte_marker = lte;
