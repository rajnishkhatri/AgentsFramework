/**
 * Architecture test for `frontend/drizzle.config.ts` (S2.1.2 / IR-NEON-5).
 *
 * Pattern 7 (Dependency Rule Enforcement Test): the test IS the tool.
 * It must (a) PASS on the live `drizzle.config.ts` and (b) FAIL when a
 * synthetic config that puts a checkpoint table into the inclusive
 * whitelist is fed through the same predicate. The second assertion
 * (the synthetic-violation block at the bottom of this file) is the
 * self-validation that the detector actually catches the regression.
 *
 * Authoritative invariant: the LangGraph checkpoint tables MUST NOT
 * appear in the drizzle-kit table set. See
 * `prompts/codeReviewer/frontend/architecture_rules.j2` →
 *   §"Sprint Story Acceptance Map" / S2.1.2
 *   §"Infra Dev-Tier Rules"        / IR-NEON-5
 */

import { describe, expect, it } from "vitest";
import liveConfig from "../../drizzle.config";

const CHECKPOINT_TABLES: ReadonlyArray<string> = [
  "checkpoints",
  "checkpoint_writes",
  "checkpoint_blobs",
  "checkpoint_migrations",
];

/**
 * Normalise `tablesFilter` (which may be a single string OR an array)
 * to a string list for the predicate. Returns an empty array when the
 * field is unset (which itself is a violation per IR-NEON-5).
 */
function asList(filter: string | string[] | undefined): string[] {
  if (filter === undefined) return [];
  return Array.isArray(filter) ? [...filter] : [filter];
}

/**
 * Authoritative IR-NEON-5 predicate. A checkpoint table is "excluded"
 * when EITHER (a) the negation form `!checkpoints` is in the filter
 * (drizzle-kit's negation glob), OR (b) the inclusive whitelist simply
 * does not name it. Returns the list of checkpoint tables that fail
 * the rule (empty array == PASS).
 */
function checkpointTablesNotExcluded(
  filter: string | string[] | undefined,
): string[] {
  const list = asList(filter);
  if (list.length === 0) {
    // No tablesFilter at all means drizzle-kit will manage every table
    // it sees — that includes the checkpoint tables.
    return [...CHECKPOINT_TABLES];
  }
  // If the list looks like a negation list (any entry starts with `!`),
  // require every checkpoint table to be explicitly negated. Otherwise
  // treat it as an inclusive whitelist and require none of the
  // checkpoint tables to be present.
  const isNegationList = list.some((s) => s.startsWith("!"));
  const offenders: string[] = [];
  for (const ck of CHECKPOINT_TABLES) {
    if (isNegationList) {
      if (!list.includes(`!${ck}`)) offenders.push(ck);
    } else {
      if (list.includes(ck)) offenders.push(ck);
    }
  }
  return offenders;
}

describe("drizzle.config tablesFilter [IR-NEON-5 / S2.1.2]", () => {
  it("declares dialect=postgresql for the Neon Postgres tier", () => {
    expect(liveConfig.dialect).toBe("postgresql");
  });

  it("excludes every LangGraph checkpoint table from the migration set", () => {
    const offenders = checkpointTablesNotExcluded(liveConfig.tablesFilter);
    expect(
      offenders,
      `IR-NEON-5 violation: drizzle-kit may regenerate ${offenders.join(", ")}`,
    ).toEqual([]);
  });

  it("uses an explicit tablesFilter (no implicit 'manage everything' default)", () => {
    expect(liveConfig.tablesFilter).toBeDefined();
    expect(asList(liveConfig.tablesFilter).length).toBeGreaterThan(0);
  });

  it("points schema + out at lib/db/ (so future migrations stay inside the lib boundary)", () => {
    expect(liveConfig.schema).toBe("./lib/db/schema.ts");
    expect(liveConfig.out).toBe("./lib/db/migrations");
  });
});

describe("Pattern 7 self-validation [IR-NEON-5]", () => {
  it("FAILS a synthetic config that puts a checkpoint table in the inclusive whitelist", () => {
    const synthetic = { tablesFilter: ["threads", "checkpoints"] };
    const offenders = checkpointTablesNotExcluded(synthetic.tablesFilter);
    expect(offenders).toContain("checkpoints");
  });

  it("FAILS a synthetic negation-list that forgets one of the checkpoint tables", () => {
    const synthetic = {
      tablesFilter: [
        "!checkpoints",
        "!checkpoint_writes",
        // Intentionally drops checkpoint_blobs + checkpoint_migrations.
      ],
    };
    const offenders = checkpointTablesNotExcluded(synthetic.tablesFilter);
    expect(offenders).toEqual(
      expect.arrayContaining(["checkpoint_blobs", "checkpoint_migrations"]),
    );
  });

  it("FAILS when tablesFilter is missing entirely", () => {
    const offenders = checkpointTablesNotExcluded(undefined);
    expect(offenders).toEqual([...CHECKPOINT_TABLES]);
  });

  it("PASSES the inclusive-whitelist that names only the application tables", () => {
    const offenders = checkpointTablesNotExcluded(["threads", "thread_messages"]);
    expect(offenders).toEqual([]);
  });

  it("PASSES the negation-list form that names every checkpoint table", () => {
    const offenders = checkpointTablesNotExcluded([
      "!checkpoints",
      "!checkpoint_writes",
      "!checkpoint_blobs",
      "!checkpoint_migrations",
    ]);
    expect(offenders).toEqual([]);
  });
});
