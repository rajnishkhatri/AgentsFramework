/**
 * FR-G3 dual-dialect parity (ADR-0005 / ADR-0010 condition #1).
 * Column-for-column identity of name across schema.pg.ts ↔ schema.sqlite.ts.
 * E1a FR-8b additionally requires the Tutorial teaching fields on both dialects.
 *
 * FR-40 / spec §4.2: exam_* tables must also match on constraints, defaults,
 * PK/FK, and indexes — not only column names.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { getTableColumns, getTableName, type Table } from "drizzle-orm";
import { getTableConfig as getPgTableConfig } from "drizzle-orm/pg-core";
import { getTableConfig as getSqliteTableConfig } from "drizzle-orm/sqlite-core";
import { describe, expect, it } from "vitest";

import * as pg from "./schema.pg";
import * as sqlite from "./schema.sqlite";

const TABLE_PAIRS: ReadonlyArray<{
  readonly name: string;
  readonly pg: Table;
  readonly sqlite: Table;
}> = [
  { name: "skill", pg: pg.skill, sqlite: sqlite.skill },
  { name: "question", pg: pg.question, sqlite: sqlite.question },
  { name: "hint", pg: pg.hint, sqlite: sqlite.hint },
  { name: "test_item", pg: pg.testItem, sqlite: sqlite.testItem },
  { name: "test_blueprint", pg: pg.testBlueprint, sqlite: sqlite.testBlueprint },
  { name: "quiz_session", pg: pg.quizSession, sqlite: sqlite.quizSession },
  { name: "attempt", pg: pg.attempt, sqlite: sqlite.attempt },
  { name: "skill_state", pg: pg.skillState, sqlite: sqlite.skillState },
  { name: "tutorial", pg: pg.tutorial, sqlite: sqlite.tutorial },
  { name: "content_string", pg: pg.contentString, sqlite: sqlite.contentString },
  { name: "progress_point", pg: pg.progressPoint, sqlite: sqlite.progressPoint },
  { name: "exam_run", pg: pg.examRun, sqlite: sqlite.examRun },
  {
    name: "exam_section_attempt",
    pg: pg.examSectionAttempt,
    sqlite: sqlite.examSectionAttempt,
  },
  { name: "exam_run_item", pg: pg.examRunItem, sqlite: sqlite.examRunItem },
];

function columnNames(table: Table): string[] {
  return Object.keys(getTableColumns(table)).sort();
}

describe("dual-dialect schema parity (FR-G3)", () => {
  it.each(TABLE_PAIRS)("$name: pg column names ≡ sqlite column names", ({ pg: pgTable, sqlite: sqliteTable }) => {
    expect(columnNames(pgTable)).toEqual(columnNames(sqliteTable));
  });
});

describe("Attempt.resolution — commit-first FR-10 dialect presence", () => {
  it("pg attempt has nullable resolution column", () => {
    expect(columnNames(pg.attempt)).toContain("resolution");
  });

  it("sqlite attempt has nullable resolution column", () => {
    expect(columnNames(sqlite.attempt)).toContain("resolution");
  });
});

describe("Tutorial teaching fields — E1a FR-8b dialect presence", () => {
  const REQUIRED = [
    "ground_md",
    "pitfall_md",
    "question_md",
    "self_explain_prompt",
    "worked_example",
    "completion_try",
    "annotated_examples",
  ] as const;

  it("pg tutorial has every teaching column", () => {
    const cols = new Set(columnNames(pg.tutorial));
    for (const c of REQUIRED) expect(cols.has(c)).toBe(true);
  });

  it("sqlite tutorial has every teaching column", () => {
    const cols = new Set(columnNames(sqlite.tutorial));
    for (const c of REQUIRED) expect(cols.has(c)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// FR-40 / spec §4.2 — exam_run, exam_section_attempt, exam_run_item
// Asserts constraints / defaults / PK-FK / indexes, not only column names.
// ---------------------------------------------------------------------------

const EXAM_RUN_COLUMNS = [
  "composite",
  "created_at",
  "form_id",
  "id",
  "learner_id",
] as const;

const EXAM_SECTION_ATTEMPT_COLUMNS = [
  "deadline_at",
  "finished_at",
  "raw_correct",
  "raw_scored_total",
  "run_id",
  "scale_score",
  "section_code",
  "started_at",
  "status",
  "time_remaining_ms_at_submit",
] as const;

const EXAM_RUN_ITEM_COLUMNS = [
  "answer_changes",
  "bookmarked",
  "chosen_letter",
  "correct",
  "dwell_at_first_answer_ms",
  "dwell_ms",
  "first_answered_at",
  "flagged_in_section",
  "ordinal",
  "question_id",
  "run_id",
  "section_code",
  "updated_at",
  "visits",
] as const;

const EXAM_EXPORTS = [
  { sqlName: "exam_run", exportName: "examRun", columns: EXAM_RUN_COLUMNS },
  {
    sqlName: "exam_section_attempt",
    exportName: "examSectionAttempt",
    columns: EXAM_SECTION_ATTEMPT_COLUMNS,
  },
  {
    sqlName: "exam_run_item",
    exportName: "examRunItem",
    columns: EXAM_RUN_ITEM_COLUMNS,
  },
] as const;

const MIGRATION_0005 = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../../drizzle/0005_exam_runs.sql",
);

function exportedTable(mod: object, exportName: string): Table | undefined {
  const value = (mod as Record<string, unknown>)[exportName];
  return value as Table | undefined;
}

function requireColumn(table: Table, name: string) {
  const col = getTableColumns(table)[name];
  if (!col) {
    throw new Error(`missing column '${name}' on ${getTableName(table)}`);
  }
  return col;
}

function constraintShape(table: Table): Record<
  string,
  { notNull: boolean; hasDefault: boolean; primary: boolean }
> {
  return Object.fromEntries(
    Object.entries(getTableColumns(table)).map(([key, col]) => [
      key,
      { notNull: col.notNull, hasDefault: col.hasDefault, primary: col.primary },
    ]),
  );
}

function dialectConfig(table: Table, dialect: "pg" | "sqlite") {
  return dialect === "pg"
    ? getPgTableConfig(table as Parameters<typeof getPgTableConfig>[0])
    : getSqliteTableConfig(table as Parameters<typeof getSqliteTableConfig>[0]);
}

function primaryKeyColumnNames(table: Table, dialect: "pg" | "sqlite"): string[] {
  const inline = Object.values(getTableColumns(table))
    .filter((c) => c.primary)
    .map((c) => c.name);
  if (inline.length > 0) return [...inline].sort();
  return (dialectConfig(table, dialect).primaryKeys[0]?.columns ?? [])
    .map((c) => c.name)
    .sort();
}

function foreignKeyShapes(
  table: Table,
  dialect: "pg" | "sqlite",
): Array<{
  from: string[];
  toTable: string;
  to: string[];
  onDelete: string | undefined;
}> {
  return dialectConfig(table, dialect).foreignKeys.map((fk) => {
    const ref = fk.reference();
    return {
      from: ref.columns.map((c) => c.name).sort(),
      toTable: getTableName(ref.foreignTable),
      to: ref.foreignColumns.map((c) => c.name).sort(),
      onDelete: fk.onDelete,
    };
  });
}

function indexShapes(
  table: Table,
  dialect: "pg" | "sqlite",
): Array<{ name: string | undefined; columns: string[] }> {
  return dialectConfig(table, dialect).indexes.map((idx) => ({
    name: idx.config.name,
    columns: idx.config.columns.map((col) => {
      if (
        col &&
        typeof col === "object" &&
        "name" in col &&
        typeof col.name === "string"
      ) {
        return col.name;
      }
      throw new Error("index column missing name");
    }),
  }));
}

describe("exam tables — FR-40 / spec §4.2", () => {
  it.each(EXAM_EXPORTS)(
    "exports $sqlName on both dialects",
    ({ exportName }) => {
      expect(exportedTable(pg, exportName)).toBeDefined();
      expect(exportedTable(sqlite, exportName)).toBeDefined();
    },
  );

  it.each(EXAM_EXPORTS)(
    "$sqlName: pg column names ≡ sqlite column names ≡ §4.2",
    ({ exportName, columns }) => {
      const pgTable = exportedTable(pg, exportName);
      const sqliteTable = exportedTable(sqlite, exportName);
      expect(pgTable).toBeDefined();
      expect(sqliteTable).toBeDefined();
      expect(columnNames(pgTable!)).toEqual([...columns]);
      expect(columnNames(sqliteTable!)).toEqual([...columns]);
    },
  );

  it.each(EXAM_EXPORTS)(
    "$sqlName: pg constraints/defaults ≡ sqlite constraints/defaults",
    ({ exportName }) => {
      const pgTable = exportedTable(pg, exportName);
      const sqliteTable = exportedTable(sqlite, exportName);
      expect(pgTable).toBeDefined();
      expect(sqliteTable).toBeDefined();
      expect(constraintShape(pgTable!)).toEqual(constraintShape(sqliteTable!));
    },
  );

  it("exam_run PK is id; created_at has a default; composite is nullable", () => {
    for (const [dialect, table] of [
      ["pg", exportedTable(pg, "examRun")],
      ["sqlite", exportedTable(sqlite, "examRun")],
    ] as const) {
      expect(table, dialect).toBeDefined();
      expect(primaryKeyColumnNames(table!, dialect)).toEqual(["id"]);
      expect(requireColumn(table!, "id").notNull).toBe(true);
      expect(requireColumn(table!, "learner_id").notNull).toBe(true);
      expect(requireColumn(table!, "form_id").notNull).toBe(true);
      expect(requireColumn(table!, "created_at").notNull).toBe(true);
      expect(requireColumn(table!, "created_at").hasDefault).toBe(true);
      expect(requireColumn(table!, "composite").notNull).toBe(false);
      expect(requireColumn(table!, "composite").hasDefault).toBe(false);
    }
  });

  it("exam_run has index (learner_id, form_id) on both dialects", () => {
    for (const [dialect, table] of [
      ["pg", exportedTable(pg, "examRun")],
      ["sqlite", exportedTable(sqlite, "examRun")],
    ] as const) {
      expect(table, dialect).toBeDefined();
      expect(indexShapes(table!, dialect)).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ columns: ["learner_id", "form_id"] }),
        ]),
      );
    }
  });

  it("exam_section_attempt PK is (run_id, section_code); run_id FK → exam_run.id CASCADE", () => {
    for (const [dialect, table] of [
      ["pg", exportedTable(pg, "examSectionAttempt")],
      ["sqlite", exportedTable(sqlite, "examSectionAttempt")],
    ] as const) {
      expect(table, dialect).toBeDefined();
      expect(primaryKeyColumnNames(table!, dialect)).toEqual([
        "run_id",
        "section_code",
      ]);
      expect(foreignKeyShapes(table!, dialect)).toEqual([
        {
          from: ["run_id"],
          toTable: "exam_run",
          to: ["id"],
          onDelete: "cascade",
        },
      ]);
      expect(requireColumn(table!, "status").notNull).toBe(true);
      expect(requireColumn(table!, "started_at").notNull).toBe(false);
      expect(requireColumn(table!, "finished_at").notNull).toBe(false);
      expect(requireColumn(table!, "deadline_at").notNull).toBe(false);
      expect(requireColumn(table!, "raw_correct").notNull).toBe(false);
      expect(requireColumn(table!, "raw_scored_total").notNull).toBe(false);
      expect(requireColumn(table!, "scale_score").notNull).toBe(false);
      expect(requireColumn(table!, "time_remaining_ms_at_submit").notNull).toBe(
        false,
      );
    }
  });

  it("exam_run_item PK is (run_id, section_code, question_id); run_id FK → exam_run.id CASCADE", () => {
    for (const [dialect, table] of [
      ["pg", exportedTable(pg, "examRunItem")],
      ["sqlite", exportedTable(sqlite, "examRunItem")],
    ] as const) {
      expect(table, dialect).toBeDefined();
      expect(primaryKeyColumnNames(table!, dialect)).toEqual([
        "question_id",
        "run_id",
        "section_code",
      ]);
      expect(foreignKeyShapes(table!, dialect)).toEqual([
        {
          from: ["run_id"],
          toTable: "exam_run",
          to: ["id"],
          onDelete: "cascade",
        },
      ]);
    }
  });

  it("exam_run_item defaults: counters 0, flags false, updated_at present; nullable answers", () => {
    for (const [dialect, table] of [
      ["pg", exportedTable(pg, "examRunItem")],
      ["sqlite", exportedTable(sqlite, "examRunItem")],
    ] as const) {
      expect(table, dialect).toBeDefined();
      expect(requireColumn(table!, "ordinal").notNull).toBe(true);
      expect(requireColumn(table!, "dwell_ms").notNull).toBe(true);
      expect(requireColumn(table!, "dwell_ms").hasDefault).toBe(true);
      expect(requireColumn(table!, "dwell_ms").default).toBe(0);
      expect(requireColumn(table!, "visits").notNull).toBe(true);
      expect(requireColumn(table!, "visits").hasDefault).toBe(true);
      expect(requireColumn(table!, "visits").default).toBe(0);
      expect(requireColumn(table!, "answer_changes").notNull).toBe(true);
      expect(requireColumn(table!, "answer_changes").hasDefault).toBe(true);
      expect(requireColumn(table!, "answer_changes").default).toBe(0);
      expect(requireColumn(table!, "flagged_in_section").notNull).toBe(true);
      expect(requireColumn(table!, "flagged_in_section").hasDefault).toBe(true);
      expect(requireColumn(table!, "flagged_in_section").default).toBe(false);
      expect(requireColumn(table!, "bookmarked").notNull).toBe(true);
      expect(requireColumn(table!, "bookmarked").hasDefault).toBe(true);
      expect(requireColumn(table!, "bookmarked").default).toBe(false);
      expect(requireColumn(table!, "updated_at").notNull).toBe(true);
      expect(requireColumn(table!, "updated_at").hasDefault).toBe(true);
      expect(requireColumn(table!, "chosen_letter").notNull).toBe(false);
      expect(requireColumn(table!, "correct").notNull).toBe(false);
      expect(requireColumn(table!, "first_answered_at").notNull).toBe(false);
      expect(requireColumn(table!, "dwell_at_first_answer_ms").notNull).toBe(
        false,
      );
    }
  });

  it("exam_run_item has index (run_id, section_code) on both dialects", () => {
    for (const [dialect, table] of [
      ["pg", exportedTable(pg, "examRunItem")],
      ["sqlite", exportedTable(sqlite, "examRunItem")],
    ] as const) {
      expect(table, dialect).toBeDefined();
      expect(indexShapes(table!, dialect)).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ columns: ["run_id", "section_code"] }),
        ]),
      );
    }
  });

  it("ENGINE_TABLE_NAMES whitelist includes the three exam tables", () => {
    expect(pg.ENGINE_TABLE_NAMES).toEqual(
      expect.arrayContaining([
        "exam_run",
        "exam_section_attempt",
        "exam_run_item",
      ]),
    );
  });

  it("drizzle/0005_exam_runs.sql creates the three tables with PK/FK/indexes", () => {
    expect(fs.existsSync(MIGRATION_0005)).toBe(true);
    const sql = fs.readFileSync(MIGRATION_0005, "utf8");
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS "exam_run"/);
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS "exam_section_attempt"/);
    expect(sql).toMatch(/CREATE TABLE IF NOT EXISTS "exam_run_item"/);
    expect(sql).toMatch(/PRIMARY KEY \("run_id", "section_code"\)/);
    expect(sql).toMatch(
      /PRIMARY KEY \("run_id", "section_code", "question_id"\)/,
    );
    expect(sql).toMatch(/REFERENCES "exam_run" \("id"\) ON DELETE CASCADE/);
    expect(sql).toMatch(/ON "exam_run" \("learner_id", "form_id"\)/);
    expect(sql).toMatch(/ON "exam_run_item" \("run_id", "section_code"\)/);
    expect(sql).toMatch(/"composite" real/);
    expect(sql).toMatch(/"created_at" timestamptz NOT NULL DEFAULT now\(\)/);
  });
});
