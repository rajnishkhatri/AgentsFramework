/**
 * FR-G3 dual-dialect parity (ADR-0005 / ADR-0010 condition #1).
 * Column-for-column identity of name across schema.pg.ts ↔ schema.sqlite.ts.
 * E1a FR-8b additionally requires the Tutorial teaching fields on both dialects.
 */

import { getTableColumns, type Table } from "drizzle-orm";
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
];

function columnNames(table: Table): string[] {
  return Object.keys(getTableColumns(table)).sort();
}

describe("dual-dialect schema parity (FR-G3)", () => {
  it.each(TABLE_PAIRS)("$name: pg column names ≡ sqlite column names", ({ pg: pgTable, sqlite: sqliteTable }) => {
    expect(columnNames(pgTable)).toEqual(columnNames(sqliteTable));
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
