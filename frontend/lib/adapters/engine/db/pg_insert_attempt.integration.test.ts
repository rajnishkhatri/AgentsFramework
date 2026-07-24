/**
 * T R.9 (d) — same-key insertAttempt through real Postgres (partial unique index).
 *
 * On-demand: set `ENGINE_PG_INTEGRATION=1` (managed Docker scratch) or
 * `ENGINE_SCRATCH_DATABASE_URL`. Not on the CI hot path — InMemory covers the
 * contract in-gate.
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import {
  afterAll,
  beforeAll,
  describe,
  expect,
  it,
} from "vitest";
import { drizzle as drizzlePg } from "drizzle-orm/node-postgres";
import { Pool } from "pg";

import type { Attempt, QuizSession } from "../../../wire/engine_entities";
import { pgEngineDbFrom } from "./drizzle_engine_db";
import { toNodePgConnectionString } from "@/lib/adapters/db/node_pg_url";
import {
  resolveScratchDatabaseUrl,
  stopScratchPg,
  type ScratchOpts,
} from "../../../../scripts/scratch_engine_pg";

const wantRun =
  Boolean(process.env.ENGINE_PG_INTEGRATION?.trim()) ||
  Boolean(process.env.ENGINE_SCRATCH_DATABASE_URL?.trim());

const INSERT_SCRATCH: ScratchOpts = {
  container: "engine-r9-insert-pg",
  port: "55434",
  dbName: "engine_r9_insert",
};

const REAL_DRIZZLE = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../../drizzle",
);

const MIGRATE_SCRIPT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../../scripts/migrate_engine.mjs",
);

function runMigrateCli(databaseUrl: string, drizzleDir: string): void {
  const res = spawnSync(process.execPath, [MIGRATE_SCRIPT], {
    encoding: "utf8",
    env: {
      ...process.env,
      DATABASE_URL: databaseUrl,
      ENGINE_DRIZZLE_DIR: drizzleDir,
    },
  });
  if ((res.status ?? 1) !== 0) {
    throw new Error(
      `migrate_engine failed:\n${res.stdout ?? ""}\n${res.stderr ?? ""}`,
    );
  }
}

describe.skipIf(!wantRun)(
  "pg insertAttempt idempotency — T R.9 (d) scratch pg",
  () => {
    let databaseUrl = "";
    let managed = false;
    let drizzleDir = "";
    let scratchOpts: ScratchOpts = INSERT_SCRATCH;
    let pool: Pool | undefined;
    let db: ReturnType<typeof pgEngineDbFrom>;

    beforeAll(() => {
      const scratch = resolveScratchDatabaseUrl(INSERT_SCRATCH);
      if (!scratch) {
        throw new Error(
          "ENGINE_PG_INTEGRATION=1 requires Docker (or ENGINE_SCRATCH_DATABASE_URL)",
        );
      }
      databaseUrl = scratch.url;
      managed = scratch.managed;
      scratchOpts = scratch.opts;

      // Numbered migrations only — skip the 7.5MB content seed for this seam.
      drizzleDir = fs.mkdtempSync(path.join(os.tmpdir(), "engine-pg-r9-"));
      for (const name of fs.readdirSync(REAL_DRIZZLE).sort()) {
        if (name.startsWith("0") && name.endsWith(".sql")) {
          fs.copyFileSync(
            path.join(REAL_DRIZZLE, name),
            path.join(drizzleDir, name),
          );
        }
      }
      // Tiny seed so runMigrate's seed_* loop is exercised without content bulk.
      fs.writeFileSync(
        path.join(drizzleDir, "seed_empty_marker.sql"),
        "SELECT 1;",
        "utf8",
      );

      runMigrateCli(databaseUrl, drizzleDir);
      pool = new Pool({
        connectionString: toNodePgConnectionString(databaseUrl),
      });
      // Swallow late disconnects if teardown races the container stop.
      pool.on("error", () => {});
      db = pgEngineDbFrom(drizzlePg(pool));
    }, 120_000);

    afterAll(async () => {
      if (pool) {
        await pool.end().catch(() => {});
        pool = undefined;
      }
      if (drizzleDir && fs.existsSync(drizzleDir)) {
        fs.rmSync(drizzleDir, { recursive: true, force: true });
      }
      if (managed) stopScratchPg(scratchOpts);
    });

    function session(over: Partial<QuizSession> = {}): QuizSession {
      return {
        id: "sess-pg-1",
        subject: "act-english",
        learner_id: "learner-pg",
        mode: "adaptive",
        skill_focus: null,
        started_at: "2026-07-22T12:00:00.000Z",
        ended_at: null,
        score_correct: 0,
        score_total: 0,
        target_count: 30,
        current_question_id: null,
        ...over,
      };
    }

    function attempt(over: Partial<Attempt> = {}): Attempt {
      return {
        id: "att-pg-1",
        subject: "act-english",
        session_id: "sess-pg-1",
        question_id: "ti-gen-aaaaaaaaaaaaaaaa",
        chosen_letter: "A",
        correct: true,
        elapsed_ms: 1000,
        used_hint: false,
        created_at: "2026-07-22T12:01:00.000Z",
        resolution: "first_try",
        idempotency_key: "11111111-1111-4111-8111-111111111111",
        ...over,
      };
    }

    it("same-key double insert → one row + typed already-existed", async () => {
      await db.insertSession(session());
      const key = "22222222-2222-4222-8222-222222222222";
      const first = await db.insertAttempt(
        attempt({ id: "att-a", idempotency_key: key }),
      );
      expect(first.status).toBe("inserted");

      const second = await db.insertAttempt(
        attempt({
          id: "att-b",
          idempotency_key: key,
          chosen_letter: "B",
        }),
      );
      expect(second.status).toBe("already-existed");
      expect(second.attempt.id).toBe("att-a");
      expect(second.attempt.chosen_letter).toBe("A");

      const rows = await db.listSessionAttempts("sess-pg-1");
      expect(rows).toHaveLength(1);
    });

    it("new key → second row", async () => {
      const third = await db.insertAttempt(
        attempt({
          id: "att-c",
          question_id: "ti-gen-bbbbbbbbbbbbbbbb",
          idempotency_key: "33333333-3333-4333-8333-333333333333",
          chosen_letter: "C",
        }),
      );
      expect(third.status).toBe("inserted");
      expect(await db.listSessionAttempts("sess-pg-1")).toHaveLength(2);
    });
  },
);
