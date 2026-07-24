/**
 * T R.9 (c) — migrate_engine.mjs replay + mid-file rollback on scratch pg.
 *
 * In-gate when Docker can start a managed scratch container (or
 * ENGINE_SCRATCH_DATABASE_URL / ENGINE_PG_INTEGRATION+DATABASE_URL). Uses a
 * tiny fixture drizzle dir (not the 7.5MB content seed) so the runner contract
 * is what we assert — ledger skip, always-apply seed, per-file ROLLBACK
 * without ledgering the failing file.
 */

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import pg from "pg";

import {
  dockerAvailable,
  resolveScratchDatabaseUrl,
  stopScratchPg,
  type ScratchOpts,
} from "./scratch_engine_pg";

const MIGRATE_SCRIPT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "migrate_engine.mjs",
);

const MIGRATE_SCRATCH: ScratchOpts = {
  container: "engine-r9-migrate-pg",
  port: "55433",
  dbName: "engine_r9_migrate",
};

const canScratch =
  Boolean(process.env.ENGINE_SCRATCH_DATABASE_URL?.trim()) ||
  (Boolean(process.env.ENGINE_PG_INTEGRATION?.trim()) &&
    Boolean(process.env.DATABASE_URL?.trim())) ||
  dockerAvailable();

type MigrateSummary = {
  ok: true;
  applied: string[];
  skipped: string[];
  numbered_total: number;
  seed_total: number;
};

function runMigrateCli(
  databaseUrl: string,
  drizzleDir: string,
): { status: number; summary: MigrateSummary | null; stderr: string; stdout: string } {
  const res = spawnSync(process.execPath, [MIGRATE_SCRIPT], {
    encoding: "utf8",
    env: {
      ...process.env,
      DATABASE_URL: databaseUrl,
      ENGINE_DRIZZLE_DIR: drizzleDir,
    },
  });
  const stdout = res.stdout ?? "";
  const stderr = res.stderr ?? "";
  const status = res.status ?? 1;
  let summary: MigrateSummary | null = null;
  const line = stdout
    .trim()
    .split("\n")
    .reverse()
    .find((l) => l.startsWith("{") && l.includes('"ok"'));
  if (line) {
    try {
      summary = JSON.parse(line) as MigrateSummary;
    } catch {
      summary = null;
    }
  }
  return { status, summary, stderr, stdout };
}

describe.skipIf(!canScratch)(
  "migrate_engine.mjs — T R.9 replay + rollback",
  () => {
    let databaseUrl = "";
    let managed = false;
    let fixtureDir = "";
    let scratchOpts: ScratchOpts = MIGRATE_SCRATCH;

    beforeAll(() => {
      const scratch = resolveScratchDatabaseUrl(MIGRATE_SCRATCH);
      if (!scratch) {
        throw new Error("scratch Postgres unavailable for migrate integration");
      }
      databaseUrl = scratch.url;
      managed = scratch.managed;
      scratchOpts = scratch.opts;
      fixtureDir = fs.mkdtempSync(path.join(os.tmpdir(), "engine-migrate-r9-"));
      fs.writeFileSync(
        path.join(fixtureDir, "0000_ok.sql"),
        `CREATE TABLE IF NOT EXISTS "r9_probe" (
         "id" text PRIMARY KEY NOT NULL,
         "v" text NOT NULL
       );`,
        "utf8",
      );
      fs.writeFileSync(
        path.join(fixtureDir, "seed_tiny.sql"),
        `INSERT INTO "r9_probe" ("id", "v") VALUES ('seed', 'v1')
       ON CONFLICT ("id") DO UPDATE SET "v" = EXCLUDED."v";`,
        "utf8",
      );
    }, 60_000);

    afterAll(() => {
      if (fixtureDir && fs.existsSync(fixtureDir)) {
        fs.rmSync(fixtureDir, { recursive: true, force: true });
      }
      if (managed) stopScratchPg(scratchOpts);
    });

    it("second run applies zero numbered and re-runs seed_*", () => {
      const first = runMigrateCli(databaseUrl, fixtureDir);
      expect(first.status).toBe(0);
      expect(first.summary).toMatchObject({
        ok: true,
        applied: ["0000_ok.sql", "seed_tiny.sql"],
        skipped: [],
      });

      const second = runMigrateCli(databaseUrl, fixtureDir);
      expect(second.status).toBe(0);
      expect(second.summary).toMatchObject({
        ok: true,
        applied: ["seed_tiny.sql"],
        skipped: ["0000_ok.sql"],
        numbered_total: 1,
        seed_total: 1,
      });
    });

    it("mid-file failure ROLLBACKs and does not ledger the failing file", async () => {
      fs.writeFileSync(
        path.join(fixtureDir, "0001_fail.sql"),
        `CREATE TABLE "r9_half" ("id" text);
       SELECT * FROM "definitely_missing_table_r9";`,
        "utf8",
      );

      const failed = runMigrateCli(databaseUrl, fixtureDir);
      expect(failed.status).not.toBe(0);
      expect(failed.stderr + failed.stdout).toMatch(
        /0001_fail\.sql failed \(rolled back\)/,
      );

      const client = new pg.Client({ connectionString: databaseUrl });
      await client.connect();
      try {
        const ledger = await client.query(
          `SELECT "filename" FROM "_frontend_migrations" ORDER BY "filename"`,
        );
        expect(ledger.rows.map((r) => r.filename)).toEqual(["0000_ok.sql"]);
        // Half-applied object from the failing file must not survive ROLLBACK.
        const half = await client.query(
          `SELECT to_regclass('public.r9_half') AS reg`,
        );
        expect(half.rows[0]?.reg).toBeNull();
      } finally {
        await client.end();
      }
    });
  },
);
